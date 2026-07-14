"""
VLM semantic pass (Phase 3, stage 2) — OCR text-in-image, brand guess,
skin-takeover confirmation, safety flags. Structured output via
function-calling-as-schema (ADR 005 — assume MaaS quirks apply to VLMs too).

Only runs when VLM_MODEL is set AND the model accepts OpenAI-style image_url
content (verify with scripts/probe_vlm.py first). Failure → caller marks the
file needs_review — a VLM outage must never silently auto-approve ⛔.
"""
import base64
import io
import json

from pydantic import BaseModel, Field

from config import config


class SafetyFlags(BaseModel):
    nsfw: bool
    alcohol: bool
    gambling: bool
    political: bool
    medical: bool


class CreativeVLMResult(BaseModel):
    ocr_text: list[str]                                  # headline/CTA/legal text found
    brand_guess: str
    subject_desc: str                                   # one line, Vietnamese
    is_skin_takeover: bool
    safety: SafetyFlags
    brief_match_score: int = Field(ge=1, le=5)
    brief_match_reasons: list[str]
    confidence: float = Field(ge=0, le=1)


_PROMPT = """Phân tích creative quảng cáo trong ảnh:
1. ocr_text: TẤT CẢ chữ đọc được trong ảnh (headline, CTA, legal text) — từng dòng.
2. brand_guess: brand/logo nhận ra được (chuỗi rỗng nếu không rõ).
3. subject_desc: mô tả 1 câu tiếng Việt cảnh/chủ thể.
4. is_skin_takeover: ảnh có phải background/skin toàn trang không?
5. safety: cờ true nếu ảnh chứa nội dung nhạy cảm loại đó.
6. brief_match_score: mức độ khớp brief từ 1-5 và brief_match_reasons.
7. confidence: độ tự tin tổng thể 0-1.
Luôn trả về đầy đủ tất cả trường, kể cả khi giá trị là chuỗi hoặc danh sách rỗng."""

_vlm_client = None


def _prepare_image(image_bytes: bytes, mime: str) -> tuple[bytes, str]:
    """Bound VLM image tokens; deterministic analysis still uses original bytes."""
    try:
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes))
        image.thumbnail((768, 768))
        if image.mode != "RGB":
            image = image.convert("RGB")
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=88, optimize=True)
        return output.getvalue(), "image/jpeg"
    except Exception:
        return image_bytes, mime


def _normalize_payload(raw: str) -> dict:
    """Normalize equivalent MaaS shapes while keeping missing fields invalid."""
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < start:
        raise ValueError("VLM returned no JSON object")
    payload = json.loads(raw[start:end + 1])

    safety = payload.get("safety")
    names = set(SafetyFlags.model_fields)
    if isinstance(safety, str) and safety.strip().startswith("{"):
        safety = json.loads(safety)
        payload["safety"] = safety
    if isinstance(safety, list):
        if any(not isinstance(item, str) for item in safety):
            raise ValueError("Unsupported VLM safety list shape")
        flagged = {item.strip().lower() for item in safety}
        unknown = flagged - names
        if unknown:
            raise ValueError(f"Unknown VLM safety flags: {sorted(unknown)}")
        payload["safety"] = {name: name in flagged for name in names}
    elif isinstance(safety, str) and safety.strip().lower() in {
        "safe", "none", "no", "false", "không", "khong",
    }:
        payload["safety"] = {name: False for name in names}
    elif safety is False:
        payload["safety"] = {name: False for name in names}
    elif safety is True:
        raise ValueError("VLM safety=true did not identify a safety category")
    elif isinstance(safety, dict):
        payload["safety"] = {
            name: bool(
                (safety.get(name) or {}).get("flag", False)
                if isinstance(safety.get(name), dict)
                else safety.get(name, False)
            )
            for name in names
        }

    if isinstance(payload.get("ocr_text"), str):
        payload["ocr_text"] = [payload["ocr_text"]] if payload["ocr_text"] else []
    if isinstance(payload.get("brief_match_reasons"), str):
        value = payload["brief_match_reasons"]
        payload["brief_match_reasons"] = [value] if value else []
    return payload


def _get_client():
    global _vlm_client
    if _vlm_client is None:
        from openai import OpenAI
        _vlm_client = OpenAI(
            base_url=config.VLM_BASE_URL or config.LLM_BASE_URL,
            api_key=config.VLM_API_KEY or config.AI_PLATFORM_API_KEY,
            timeout=config.CREATIVE_ANALYSIS_TIMEOUT_SECONDS,
            max_retries=0,
        )
    return _vlm_client


def analyze_image_sync(
    image_bytes: bytes,
    mime: str = "image/png",
    brief: dict | None = None,
) -> CreativeVLMResult:
    """Blocking — call via asyncio.to_thread. Raises on any failure."""
    if not config.VLM_MODEL:
        raise RuntimeError("VLM_MODEL not configured")
    image_bytes, mime = _prepare_image(image_bytes, mime)
    b64 = base64.b64encode(image_bytes).decode()
    client = _get_client()
    brief = brief or {}
    brief_context = (
        f"\nBrief chiến dịch: brand={brief.get('brand', '')}; "
        f"objective={brief.get('objective', '')}; kpi={brief.get('kpi', '')}; "
        f"notes={brief.get('notes', '')[:600]}. "
        "Trả thêm brief_match_score (1-5) và brief_match_reasons."
    )
    resp = client.chat.completions.create(
        model=config.VLM_MODEL,
        max_tokens=800,
        temperature=0.1,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": _PROMPT + brief_context},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]}],
        tools=[{"type": "function", "function": {
            "name": "submit_analysis",
            "description": "Submit the creative analysis",
            "parameters": CreativeVLMResult.model_json_schema(),
        }}],
        tool_choice={"type": "function", "function": {"name": "submit_analysis"}},
    )
    msg = resp.choices[0].message
    raw = msg.tool_calls[0].function.arguments if msg.tool_calls else (msg.content or "")
    return CreativeVLMResult.model_validate(_normalize_payload(raw))
