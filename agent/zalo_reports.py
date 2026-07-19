"""Zalo-native presentation of the existing campaign report module."""
from __future__ import annotations

from collections import defaultdict
import io
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
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf",
        ] if bold else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "C:/Windows/Fonts/arial.ttf", "DejaVuSans.ttf", "arial.ttf",
        ]
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
        row["vi_sum"] += float(record.get("vi", record.get("viewability", 0)) or 0)
        row["count"] += 1
    result = []
    for day in sorted(grouped):
        row = grouped[day]
        row["date"] = day
        row["ctr"] = row["clicks"] / row["impressions"] * 100 if row["impressions"] else 0
        row["cpm"] = row["spend"] / row["impressions"] * 1000 if row["impressions"] else 0
        row["cvr"] = row["conversions"] / row["clicks"] * 100 if row["clicks"] else 0
        row["cpa"] = row["spend"] / row["conversions"] if row["conversions"] else 0
        row["frequency"] = row["impressions"] / row["reach"] if row["reach"] else 0
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
    total["frequency"] = total["impressions"] / total["reach"] if total["reach"] else 0
    vi_values = [
        float(row.get("vi", row.get("viewability", 0)) or 0)
        for row in records if row.get("vi") is not None or row.get("viewability") is not None
    ]
    total["viewability"] = sum(vi_values) / len(vi_values) if vi_values else 0
    return total


def _zone_rows(records: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = defaultdict(lambda: {
        "impressions": 0.0, "clicks": 0.0, "spend": 0.0,
        "reach": 0.0, "conversions": 0.0, "vi_sum": 0.0, "count": 0,
    })
    for record in records:
        zone = str(
            record.get("placementId") or record.get("placement_id")
            or record.get("placement") or record.get("zone") or "Không rõ"
        )
        row = grouped[zone]
        for key in ("impressions", "clicks", "spend", "reach", "conversions"):
            row[key] += float(record.get(key) or 0)
        row["vi_sum"] += float(record.get("vi", record.get("viewability", 0)) or 0)
        row["count"] += 1
    result = []
    for zone, row in grouped.items():
        row["zone"] = zone.replace("_", " ")
        row["ctr"] = row["clicks"] / row["impressions"] * 100 if row["impressions"] else 0
        row["cpm"] = row["spend"] / row["impressions"] * 1000 if row["impressions"] else 0
        row["frequency"] = row["impressions"] / row["reach"] if row["reach"] else 0
        row["viewability"] = row["vi_sum"] / row["count"] if row["count"] else 0
        result.append(row)
    return sorted(result, key=lambda item: item["impressions"], reverse=True)


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


def _value_label(key: str, value: float) -> str:
    if key in {"ctr", "cvr", "viewability"}:
        return f"{value:.2f}%"
    if key == "frequency":
        return f"{value:.2f}"
    if key in {"spend", "cpm", "cpa"}:
        return f"{_fmt_number(value)} đ"
    return _fmt_number(value)


def _metric_cards(totals: dict) -> list[tuple[str, str]]:
    return [
        ("Impressions", _fmt_number(totals["impressions"])),
        ("Clicks", _fmt_number(totals["clicks"])),
        ("CTR", f"{totals['ctr']:.2f}%"),
        ("Spend", f"{_fmt_number(totals['spend'])} đ"),
        ("Reach", _fmt_number(totals["reach"])),
        ("Viewability", f"{totals['viewability']:.2f}%"),
    ]


def _new_page(campaign: dict, view: str, page: int, subtitle: str):
    width, height = 1080, 1350
    image = Image.new("RGB", (width, height), "#f4f7fb")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 205), fill="#10233f")
    draw.text((58, 34), "CAMP ADS", font=_font(22, True), fill="#84d8ef")
    draw.text((58, 72), f"{REPORT_CATALOG[view]['label']} Report", font=_font(43, True), fill="#ffffff")
    brand = str((campaign.get("order") or {}).get("brand") or campaign.get("campaign_id") or "Campaign")
    draw.text((58, 132), brand[:48], font=_font(24), fill="#d9e6f7")
    marker = f"{page}/3 · {subtitle}"
    marker_width = draw.textbbox((0, 0), marker, font=_font(19, True))[2]
    draw.text((1022 - marker_width, 145), marker, font=_font(19, True), fill="#84d8ef")
    return image, draw


def _panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str) -> tuple[int, int, int, int]:
    draw.rounded_rectangle(box, radius=22, fill="#ffffff", outline="#dbe5f1", width=2)
    draw.text((box[0] + 25, box[1] + 20), title, font=_font(23, True), fill="#203858")
    return box[0] + 30, box[1] + 70, box[2] - 30, box[3] - 30


def _line_chart(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], rows: list[dict], keys: list[str], colors: list[str]) -> None:
    x1, y1, x2, y2 = box
    draw.line((x1, y2, x2, y2), fill="#d7e1ed", width=2)
    for grid in range(1, 4):
        y = y1 + (y2 - y1) * grid / 4
        draw.line((x1, y, x2, y), fill="#edf2f7", width=1)
    for series_index, key in enumerate(keys):
        values = [float(row.get(key) or 0) for row in rows]
        maximum = max(values or [1]) or 1
        points = []
        for index, value in enumerate(values):
            x = x1 + (x2 - x1) * index / max(1, len(values) - 1)
            y = y2 - (y2 - y1) * value / maximum
            points.append((x, y))
        if len(points) > 1:
            draw.line(points, fill=colors[series_index], width=5, joint="curve")
        for x, y in points:
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=colors[series_index])
    if rows:
        draw.text((x1, y2 + 10), rows[0]["date"][5:], font=_font(16), fill="#65758b")
        last = rows[-1]["date"][5:]
        w = draw.textbbox((0, 0), last, font=_font(16))[2]
        draw.text((x2 - w, y2 + 10), last, font=_font(16), fill="#65758b")
    legend_x = x1
    for key, color in zip(keys, colors):
        draw.rectangle((legend_x, y2 + 42, legend_x + 22, y2 + 58), fill=color)
        draw.text((legend_x + 30, y2 + 39), key.upper(), font=_font(16, True), fill="#65758b")
        legend_x += 175


def _bar_chart(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], rows: list[dict], key: str, color: str = "#12b981") -> None:
    x1, y1, x2, y2 = box
    values = [float(row.get(key) or 0) for row in rows]
    maximum = max(values or [1]) or 1
    count = max(1, len(rows))
    gap = 10
    bar_width = max(18, int((x2 - x1 - gap * (count - 1)) / count))
    for index, (row, value) in enumerate(zip(rows, values)):
        bx = x1 + index * (bar_width + gap)
        by = y2 - (y2 - y1) * value / maximum
        draw.rounded_rectangle((bx, by, bx + bar_width, y2), radius=5, fill=color)
        if index in {0, len(rows) - 1}:
            label = row.get("date", "")[5:]
            draw.text((bx, y2 + 10), label, font=_font(14), fill="#65758b")


def _placement_bars(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], rows: list[dict], key: str) -> None:
    x1, y1, x2, y2 = box
    rows = rows[:6]
    maximum = max([float(row.get(key) or 0) for row in rows] or [1]) or 1
    row_height = max(55, int((y2 - y1) / max(1, len(rows))))
    for index, row in enumerate(rows):
        y = y1 + index * row_height
        label = str(row["zone"])[:34]
        value = float(row.get(key) or 0)
        draw.text((x1, y), label, font=_font(17, True), fill="#253d5d")
        value_label = _value_label(key, value)
        value_w = draw.textbbox((0, 0), value_label, font=_font(16))[2]
        draw.text((x2 - value_w, y), value_label, font=_font(16), fill="#65758b")
        bar_y = y + 27
        draw.rounded_rectangle((x1, bar_y, x2, bar_y + 17), radius=8, fill="#e8eef5")
        draw.rounded_rectangle((x1, bar_y, x1 + (x2 - x1) * value / maximum, bar_y + 17), radius=8, fill="#12b981")


def _page_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=84, optimize=True, progressive=True)
    return output.getvalue()


def _chart_config(view: str) -> tuple[tuple[str, list[str]], tuple[str, list[str]], tuple[str, str]]:
    configs = {
        "daily_ops": (("Nhịp phân phối hằng ngày", ["impressions", "clicks"]), ("Chi tiêu & CTR", ["spend", "ctr"]), ("Impressions theo placement", "impressions")),
        "awareness": (("Daily Reach & Impression Trend", ["reach", "impressions"]), ("CPM Trend & Period Benchmark", ["cpm"]), ("Viewability by Placement", "viewability")),
        "consideration": (("Clicks & CTR Trend", ["clicks", "ctr"]), ("CPM Trend", ["cpm"]), ("CTR theo placement", "ctr")),
        "conversion": (("Conversions & CVR Trend", ["conversions", "cvr"]), ("CPA & Spend Trend", ["cpa", "spend"]), ("Conversions theo placement", "conversions")),
        "retention": (("Reach & Frequency Trend", ["reach", "frequency"]), ("CTR Trend", ["ctr"]), ("Frequency theo placement", "frequency")),
        "executive": (("Spend & Impressions Trend", ["spend", "impressions"]), ("CTR & Conversions Trend", ["ctr", "conversions"]), ("Spend theo placement", "spend")),
    }
    return configs[view]


def render_report_images(*, campaign: dict, view: str, records: list[dict], analysis: dict) -> list[bytes]:
    """Render the full web-report information into three Zalo-safe JPEG pages."""
    if view not in REPORT_CATALOG:
        raise ValueError("unknown report view")
    totals, daily, zones = _metrics(records), _daily_rows(records)[-14:], _zone_rows(records)
    primary, secondary, placement = _chart_config(view)
    colors = ["#6f4ef6", "#20aee8"]

    page1, draw1 = _new_page(campaign, view, 1, "Tổng quan")
    insight_box = (40, 228, 1040, 400)
    draw1.rounded_rectangle(insight_box, radius=22, fill="#f0edff", outline="#c9bdfd", width=2)
    draw1.text((66, 248), "Nhận định chính", font=_font(22, True), fill="#5532d6")
    overall = re.sub(r"[*#`]+", "", str(analysis.get("overall") or "Chưa có nhận định tổng quan."))
    y = 291
    for line in _wrap(draw1, overall, _font(19), 920)[:4]:
        draw1.text((66, y), line, font=_font(19), fill="#392b75")
        y += 27
    cards = _metric_cards(totals)
    card_colors = ["#edf5ff", "#fff7df", "#eafaf0", "#f1edff", "#fff0f5", "#e9fbff"]
    for index, (label, value) in enumerate(cards):
        row, column = divmod(index, 3)
        x1, y1 = 40 + column * 340, 425 + row * 145
        draw1.rounded_rectangle((x1, y1, x1 + 320, y1 + 125), radius=20, fill=card_colors[index], outline="#d9e3ef")
        draw1.text((x1 + 22, y1 + 20), label.upper(), font=_font(17, True), fill="#65758b")
        draw1.text((x1 + 22, y1 + 59), value, font=_font(31, True), fill="#163b6c")
    chart_box = _panel(draw1, (40, 742, 1040, 1308), primary[0])
    _line_chart(draw1, (chart_box[0], chart_box[1] + 15, chart_box[2], chart_box[3] - 70), daily, primary[1], colors[:len(primary[1])])

    page2, draw2 = _new_page(campaign, view, 2, "Chất lượng phân phối")
    chart2 = _panel(draw2, (40, 228, 1040, 710), secondary[0])
    secondary_plot = (chart2[0], chart2[1] + 10, chart2[2], chart2[3] - 70)
    _line_chart(draw2, secondary_plot, daily, secondary[1], ["#f59e0b", "#6f4ef6"][:len(secondary[1])])
    if view == "awareness" and daily:
        cpm_values = [float(row.get("cpm") or 0) for row in daily]
        cpm_maximum = max(cpm_values or [1]) or 1
        cpm_average = sum(cpm_values) / len(cpm_values)
        average_y = secondary_plot[3] - (
            secondary_plot[3] - secondary_plot[1]
        ) * cpm_average / cpm_maximum
        for start in range(secondary_plot[0], secondary_plot[2], 24):
            draw2.line(
                (start, average_y, min(start + 13, secondary_plot[2]), average_y),
                fill="#8b98a9", width=2,
            )
        average_label = f"AVG {_fmt_number(cpm_average)} đ"
        label_width = draw2.textbbox((0, 0), average_label, font=_font(15, True))[2]
        draw2.text(
            (secondary_plot[2] - label_width, average_y + 7), average_label,
            font=_font(15, True), fill="#68778a",
        )
    zone_panel = _panel(draw2, (40, 735, 1040, 1308), placement[0])
    _placement_bars(draw2, zone_panel, zones, placement[1])

    page3, draw3 = _new_page(campaign, view, 3, "Chi tiết vận hành")
    distribution = _panel(draw3, (40, 228, 1040, 665), "Frequency Distribution — Daily Impressions")
    _bar_chart(draw3, (distribution[0], distribution[1] + 8, distribution[2], distribution[3] - 38), daily, "impressions")
    table_box = (40, 690, 1040, 1308)
    _panel(draw3, table_box, "Zone Performance")
    columns = [(65, "Zone"), (500, "Imps"), (630, "CTR"), (730, "VI%"), (825, "CPM"), (930, "Conv")]
    header_y = 770
    for x, label in columns:
        draw3.text((x, header_y), label, font=_font(17, True), fill="#52647a")
    draw3.line((65, 805, 1015, 805), fill="#d9e3ef", width=2)
    for index, row in enumerate(zones[:7]):
        y = 824 + index * 62
        values = [
            str(row["zone"])[:30], _fmt_number(row["impressions"]), f"{row['ctr']:.2f}%",
            f"{row['viewability']:.2f}%", _fmt_number(row["cpm"]), _fmt_number(row["conversions"]),
        ]
        for (x, _), value in zip(columns, values):
            draw3.text((x, y), value, font=_font(16, bold=(x == 65)), fill="#243a57")
        draw3.line((65, y + 42, 1015, y + 42), fill="#edf2f7", width=1)
    return [_page_bytes(page1), _page_bytes(page2), _page_bytes(page3)]


def render_report_image(*, campaign: dict, view: str, records: list[dict], analysis: dict) -> bytes:
    """Backward-compatible first page for callers that expect one image."""
    return render_report_images(campaign=campaign, view=view, records=records, analysis=analysis)[0]


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


async def get_report_bundle(*, campaign: dict, view: str, mode: str, question: str = "") -> dict:
    """Fetch existing report artifacts and prepare images, analysis, or PDF."""
    if view not in REPORT_CATALOG:
        return {"ok": False, "error": "unknown_report_type"}

    from handlers.report import handle_report_entry
    from session import get_or_create_session

    session = await get_or_create_session(campaign["session_id"])
    context = (session.get("form_state") or {}).get("report_context") or {}
    if str(context.get("campaignId") or "") != str(campaign["campaign_id"]):
        await handle_report_entry(campaign["session_id"], suppress_message=True)

    campaign_id = campaign["campaign_id"]
    async with httpx.AsyncClient(timeout=30) as client:
        status_response = await client.get(f"{config.BACKEND_URL}/api/reports/status/{campaign_id}")
        status_response.raise_for_status()
        status = status_response.json()
        type_status = (status.get("types") or {}).get(view)
        if type_status != "ready":
            return {
                "ok": True, "status": "generating" if type_status in {None, "generating"} else type_status,
                "view": view, "report": REPORT_CATALOG[view],
                "message": "Báo cáo đang được tạo. Hãy thử lại sau ít phút.",
            }
        if mode == "pdf":
            pdf_response = await client.get(f"{config.BACKEND_URL}/api/reports/export/{campaign_id}/pdf")
            pdf_response.raise_for_status()
            return {
                "ok": True, "status": "ready", "view": view,
                "report": REPORT_CATALOG[view], "pdf_bytes": pdf_response.content,
                "pdf_content_type": "application/pdf",
            }
        analysis_response = await client.get(f"{config.BACKEND_URL}/api/reports/analysis/{campaign_id}/{view}")
        data_response = await client.get(f"{config.BACKEND_URL}/api/reports/data/{campaign_id}")
        analysis_response.raise_for_status()
        data_response.raise_for_status()
        analysis, records = analysis_response.json(), data_response.json()

    suggestions = [str(item.get("question") or "") for item in analysis.get("questions") or [] if item.get("question")]
    result = {
        "ok": True, "status": "ready", "view": view, "report": REPORT_CATALOG[view],
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

    result["image_pages"] = render_report_images(
        campaign=campaign, view=view, records=records, analysis=analysis,
    )
    result["image_content_type"] = "image/jpeg"
    return result
