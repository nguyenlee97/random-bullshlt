"""
VLM semantic pass (Phase 3, stage 2) — OCR text-in-image, brand guess,
skin-takeover confirmation, safety flags. Structured output via
function-calling-as-schema (ADR 005 — assume MaaS quirks apply to VLMs too).

Only runs when VLM_MODEL is set AND the model accepts OpenAI-style image_url
content (verify with scripts/probe_vlm.py first). Failure → caller marks the
file needs_review — a VLM outage must never silently auto-approve ⛔.
"""
import base64

from pydantic import BaseModel, Field

from config import config


class SafetyFlags(BaseModel):
    nsfw: bool = False
    alcohol: bool = False
    gambling: bool = False
    political: bool = False
    medical: bool = False


class CreativeVLMResult(BaseModel):
    ocr_text: list[str] = Field(default_factory=list)   # headline/CTA/legal text found
    brand_guess: str = ""
    subject_desc: str = ""                              # one line, Vietnamese
    is_skin_takeover: bool = False
    safety: SafetyFlags = Field(default_factory=SafetyFlags)
    confidence: float = Field(ge=0, le=1, default=0.5)


_PROMPT = """Phân tích creative quảng cáo trong ảnh:
1. ocr_text: TẤT CẢ chữ đọc được trong ảnh (headline, CTA, legal text) — từng dòng.
2. brand_guess: brand/logo nhận ra được (chuỗi rỗng nếu không rõ).
3. subject_desc: mô tả 1 câu tiếng Việt cảnh/chủ thể.
4. is_skin_takeover: ảnh có phải background/skin toàn trang không?
5. safety: cờ true nếu ảnh chứa nội dung nhạy cảm loại đó.
6. confidence: độ tự tin tổng thể 0-1."""

_vlm_client = None


def _get_client():
    global _vlm_client
    if _vlm_client is None:
        from openai import OpenAI
        _vlm_client = OpenAI(
            base_url=config.VLM_BASE_URL or config.LLM_BASE_URL,
            api_key=config.VLM_API_KEY or config.AI_PLATFORM_API_KEY,
        )
    return _vlm_client


def analyze_image_sync(image_bytes: bytes, mime: str = "image/png") -> CreativeVLMResult:
    """Blocking — call via asyncio.to_thread. Raises on any failure."""
    if not config.VLM_MODEL:
        raise RuntimeError("VLM_MODEL not configured")
    b64 = base64.b64encode(image_bytes).decode()
    client = _get_client()
    resp = client.chat.completions.create(
        model=config.VLM_MODEL,
        max_tokens=1500,
        temperature=0.1,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": _PROMPT},
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
    start, end = raw.find("{"), raw.rfind("}")
    return CreativeVLMResult.model_validate_json(raw[start:end + 1])
