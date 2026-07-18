"""Zalo-native presentation of the existing synthetic report module."""
from __future__ import annotations

from collections import defaultdict
import io
import math
import re
import unicodedata

import httpx
from PIL import Image, ImageDraw, ImageFont

from config import config


REPORT_CATALOG = {
    "daily_ops": {
        "label": "Daily Ops",
        "description": "Theo dõi nhịp chi tiêu, impression, click và sức khỏe vận hành hằng ngày.",
    },
    "awareness": {
        "label": "Awareness",
        "description": "Đo độ phủ, tần suất, CPM và khả năng hiển thị của quảng cáo.",
    },
    "consideration": {
        "label": "Consideration",
        "description": "Phân tích click, CTR và chất lượng tương tác theo ngày/placement.",
    },
    "conversion": {
        "label": "Conversion",
        "description": "Xem funnel, conversion, CVR, CPA và hiệu quả chi phí.",
    },
    "retention": {
        "label": "Retention",
        "description": "Theo dõi reach lặp lại, tần suất và xu hướng suy giảm tương tác.",
    },
    "executive": {
        "label": "Executive",
        "description": "Bản tóm tắt quản trị xuyên suốt chi tiêu, hiệu suất và funnel.",
    },
}


def report_catalog_for_model() -> list[dict]:
    return [
        {"view": view, "label": item["label"], "description": item["description"]}
        for view, item in REPORT_CATALOG.items()
    ]


def _font(size: int, bold: bool = False):
    names = (
        ["DejaVuSans-Bold.ttf", "arialbd.ttf"] if bold
        else ["DejaVuSans.ttf", "arial.ttf"]
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fmt_number(value: float) -> str:
    value = float(value or 0)
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.0f}"


def _daily_rows(records: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = defaultdict(lambda: {
        "impressions": 0.0, "clicks": 0.0, "spend": 0.0,
        "reach": 0.0, "conversions": 0.0, "vi_sum": 0.0, "count": 0,
    })
    for record in records:
        day = str(record.get("date") or "?")[:10]
        row = grouped[day]
        for key in ("impressions", "clicks", "spend", "reach", "conversions"):
            row[key] += float(record.get(key) or 0)
        row["vi_sum"] += float(record.get("vi") or 0)
        row["count"] += 1
    result = []
    for day in sorted(grouped):
        row = grouped[day]
        row["date"] = day
        row["ctr"] = row["clicks"] / row["impressions"] * 100 if row["impressions"] else 0
        row["viewability"] = row["vi_sum"] / row["count"] if row["count"] else 0
        result.append(row)
    return result


def _metrics(records: list[dict]) -> dict:
    total = {
        key: sum(float(row.get(key) or 0) for row in records)
        for key in ("impressions", "clicks", "spend", "reach", "conversions")
    }
    total["ctr"] = total["clicks"] / total["impressions"] * 100 if total["impressions"] else 0
    total["cpm"] = total["spend"] / total["impressions"] * 1000 if total["impressions"] else 0
    total["cvr"] = total["conversions"] / total["clicks"] * 100 if total["clicks"] else 0
    total["cpa"] = total["spend"] / total["conversions"] if total["conversions"] else 0
    vi_values = [float(row.get("vi") or 0) for row in records if row.get("vi") is not None]
    total["viewability"] = sum(vi_values) / len(vi_values) if vi_values else 0
    return total


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = str(text or "").split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _metric_cards(view: str, totals: dict) -> list[tuple[str, str]]:
    options = {
        "daily_ops": [("Chi tiêu", f"{_fmt_number(totals['spend'])} đ"), ("Impression", _fmt_number(totals["impressions"])), ("Click", _fmt_number(totals["clicks"])), ("CTR", f"{totals['ctr']:.2f}%")],
        "awareness": [("Reach", _fmt_number(totals["reach"])), ("Impression", _fmt_number(totals["impressions"])), ("CPM", f"{_fmt_number(totals['cpm'])} đ"), ("Viewability", f"{totals['viewability']:.1f}%")],
        "consideration": [("Click", _fmt_number(totals["clicks"])), ("CTR", f"{totals['ctr']:.2f}%"), ("CPM", f"{_fmt_number(totals['cpm'])} đ"), ("Impression", _fmt_number(totals["impressions"]))],
        "conversion": [("Conversion", _fmt_number(totals["conversions"])), ("CVR", f"{totals['cvr']:.2f}%"), ("CPA", f"{_fmt_number(totals['cpa'])} đ"), ("Click", _fmt_number(totals["clicks"]))],
        "retention": [("Reach", _fmt_number(totals["reach"])), ("Tần suất", f"{totals['impressions'] / totals['reach']:.2f}" if totals["reach"] else "0"), ("CTR", f"{totals['ctr']:.2f}%"), ("Viewability", f"{totals['viewability']:.1f}%")],
        "executive": [("Chi tiêu", f"{_fmt_number(totals['spend'])} đ"), ("Reach", _fmt_number(totals["reach"])), ("CTR", f"{totals['ctr']:.2f}%"), ("Conversion", _fmt_number(totals["conversions"]))],
    }
    return options[view]


def render_report_image(*, campaign: dict, view: str, records: list[dict], analysis: dict) -> bytes:
    """Render a compact Zalo report card from the web report's backing data."""
    if view not in REPORT_CATALOG:
        raise ValueError("unknown report view")
    width, height = 1080, 1350
    image = Image.new("RGB", (width, height), "#f4f7fb")
    draw = ImageDraw.Draw(image)
    dark, blue, cyan, muted, white = "#10233f", "#2166f3", "#35b6d4", "#65758b", "#ffffff"

    draw.rectangle((0, 0, width, 230), fill=dark)
    draw.text((64, 46), "CAMP ADS", font=_font(25, True), fill="#84d8ef")
    title = f"{REPORT_CATALOG[view]['label']} Report"
    draw.text((64, 89), title, font=_font(49, True), fill=white)
    brand = str((campaign.get("order") or {}).get("brand") or campaign.get("campaign_id") or "Campaign")
    draw.text((64, 158), brand[:48], font=_font(27), fill="#d9e6f7")
    badge = "DỮ LIỆU MÔ PHỎNG"
    badge_font = _font(18, True)
    badge_w = draw.textbbox((0, 0), badge, font=badge_font)[2] + 38
    draw.rounded_rectangle((width - badge_w - 64, 50, width - 64, 91), radius=18, fill="#214b70")
    draw.text((width - badge_w - 45, 61), badge, font=badge_font, fill="#9de7f5")

    totals = _metrics(records)
    for index, (label, value) in enumerate(_metric_cards(view, totals)):
        x1 = 58 + index * 250
        x2 = x1 + 228
        draw.rounded_rectangle((x1, 264, x2, 405), radius=22, fill=white)
        draw.text((x1 + 24, 291), label, font=_font(19, True), fill=muted)
        draw.text((x1 + 24, 334), value, font=_font(30, True), fill=dark)

    # Daily trend uses the metric most relevant to the selected report.
    trend_key = {
        "daily_ops": "spend", "awareness": "reach", "consideration": "ctr",
        "conversion": "conversions", "retention": "reach", "executive": "spend",
    }[view]
    daily = _daily_rows(records)[-14:]
    chart = (58, 444, 1022, 813)
    draw.rounded_rectangle(chart, radius=24, fill=white)
    draw.text((88, 473), f"Xu hướng 14 ngày — {trend_key.upper()}", font=_font(23, True), fill=dark)
    plot = (96, 538, 984, 747)
    draw.line((plot[0], plot[3], plot[2], plot[3]), fill="#d9e2ef", width=2)
    values = [float(row.get(trend_key) or 0) for row in daily]
    maximum = max(values or [1]) or 1
    points = []
    for index, value in enumerate(values):
        x = plot[0] + (plot[2] - plot[0]) * index / max(1, len(values) - 1)
        y = plot[3] - (plot[3] - plot[1]) * value / maximum
        points.append((x, y))
    if len(points) > 1:
        draw.line(points, fill=blue, width=6, joint="curve")
    for x, y in points:
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=cyan, outline=white, width=2)
    if daily:
        draw.text((96, 765), daily[0]["date"][5:], font=_font(17), fill=muted)
        last_label = daily[-1]["date"][5:]
        label_w = draw.textbbox((0, 0), last_label, font=_font(17))[2]
        draw.text((984 - label_w, 765), last_label, font=_font(17), fill=muted)

    draw.rounded_rectangle((58, 846, 1022, 1278), radius=24, fill=white)
    draw.text((88, 878), "Nhận định chính", font=_font(25, True), fill=dark)
    overall = re.sub(r"[*#`]+", "", str(analysis.get("overall") or "Chưa có nhận định tổng quan."))
    body_font = _font(21)
    y = 929
    for line in _wrap(draw, overall, body_font, 875)[:8]:
        draw.text((90, y), line, font=body_font, fill="#32445b")
        y += 35
    if analysis.get("questions"):
        draw.text((90, 1198), "Hỏi tiếp trên Zalo để xem phân tích chi tiết.", font=_font(18, True), fill=blue)

    draw.text((58, 1310), "Generated from the existing Camp Ads synthetic report module", font=_font(16), fill="#8391a5")
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=86, optimize=True, progressive=True)
    return output.getvalue()


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", str(value or "").lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").replace("đ", "d")


def _matched_question(analysis: dict, question: str) -> dict | None:
    query = set(re.findall(r"[a-z0-9]+", _fold(question)))
    stop = {"toi", "cho", "xem", "ve", "cua", "no", "nay", "bao", "cao", "the", "nao", "la", "gi"}
    query -= stop
    best, best_score = None, 0.0
    for item in analysis.get("questions") or []:
        candidate = set(re.findall(r"[a-z0-9]+", _fold(item.get("question") or ""))) - stop
        overlap = len(query & candidate)
        score = overlap / max(1, min(len(query), len(candidate)))
        if _fold(question) in _fold(item.get("question") or "") or _fold(item.get("question") or "") in _fold(question):
            score += 1
        if score > best_score:
            best, best_score = item, score
    return best if best_score >= 0.34 else None


async def get_report_bundle(
    *, campaign: dict, view: str, mode: str, question: str = "",
) -> dict:
    """Fetch existing report artifacts and optionally render their Zalo image."""
    if view not in REPORT_CATALOG:
        return {"ok": False, "error": "unknown_report_type"}

    from handlers.report import handle_report_entry
    from session import get_or_create_session

    session = await get_or_create_session(campaign["session_id"])
    context = (session.get("form_state") or {}).get("report_context") or {}
    if str(context.get("campaignId") or "") != str(campaign["campaign_id"]):
        await handle_report_entry(campaign["session_id"], suppress_message=True)

    campaign_id = campaign["campaign_id"]
    async with httpx.AsyncClient(timeout=15) as client:
        status_response = await client.get(f"{config.BACKEND_URL}/api/reports/status/{campaign_id}")
        status_response.raise_for_status()
        status = status_response.json()
        type_status = (status.get("types") or {}).get(view)
        if type_status != "ready":
            return {
                "ok": True, "status": "generating" if type_status in {None, "generating"} else type_status,
                "view": view, "report": REPORT_CATALOG[view],
                "message": "Báo cáo đang được tạo từ dữ liệu mô phỏng. Hãy thử lại sau ít phút.",
            }
        analysis_response, data_response = await client.get(
            f"{config.BACKEND_URL}/api/reports/analysis/{campaign_id}/{view}"
        ), await client.get(f"{config.BACKEND_URL}/api/reports/data/{campaign_id}")
        analysis_response.raise_for_status()
        data_response.raise_for_status()
        analysis, records = analysis_response.json(), data_response.json()

    suggestions = [str(item.get("question") or "") for item in analysis.get("questions") or [] if item.get("question")]
    result = {
        "ok": True, "status": "ready", "data_class": "synthetic_demo",
        "view": view, "report": REPORT_CATALOG[view],
        "overall": analysis.get("overall") or "", "suggested_questions": suggestions,
    }
    if mode == "question":
        matched = _matched_question(analysis, question)
        result["question"] = question
        result["matched_analysis"] = matched
        if not matched:
            result["available_analyses"] = [
                {"question": item.get("question"), "answer": item.get("answer")}
                for item in (analysis.get("questions") or [])[:6]
            ]
        return result

    result["image_bytes"] = render_report_image(
        campaign=campaign, view=view, records=records, analysis=analysis,
    )
    result["image_content_type"] = "image/jpeg"
    return result
