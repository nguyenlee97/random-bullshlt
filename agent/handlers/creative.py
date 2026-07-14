"""
Creative handler — Step 1. Rule-based validation, NO LLM.
Validates format, dimensions, file size. Suggests matching zones by ratio.
"""
import re
from models import AgentResponse, CreativeData, ResponseMeta
from session import update_form_state, log_event

ALLOWED_FORMATS = {"image/png", "image/jpeg", "image/jpg", "image/gif", "video/mp4", "video/webm"}
MIN_WIDTH = 300
MIN_HEIGHT = 50
MAX_SIZE_MB = 10


def _fmt_bytes(b: int) -> str:
    return f"{b / 1_000_000:.1f} MB"


async def handle_creative(creative: CreativeData, session_id: str) -> AgentResponse:
    files = creative.files
    if not files:
        return AgentResponse(
            text="⚠ Anh/Chị chưa upload file nào.",
            blocks=[{"type": "info", "text": "Vui lòng upload ít nhất 1 file creative."}],
            meta=ResponseMeta(tool="creative_validate", model="none", step=1),
        )

    # ── Validate each file ────────────────────────────────────────────────────
    file_rows = []
    all_warnings = []
    valid_count = 0

    for f in files:
        issues = []
        if f.type and f.type not in ALLOWED_FORMATS:
            issues.append(f"Format {f.type} không hỗ trợ")
        if f.width > 0 and f.width < MIN_WIDTH:
            issues.append(f"Chiều rộng {f.width}px < {MIN_WIDTH}px")
        if f.height > 0 and f.height < MIN_HEIGHT:
            issues.append(f"Chiều cao {f.height}px < {MIN_HEIGHT}px")
        if f.size > MAX_SIZE_MB * 1_000_000:
            issues.append(f"File {_fmt_bytes(f.size)} > {MAX_SIZE_MB}MB")

        status = "⚠ " + " · ".join(issues) if issues else "✅ Hợp lệ"
        if not issues:
            valid_count += 1
        else:
            all_warnings.extend(issues)

        dims = f"{f.width}×{f.height}" if f.width and f.height else "—"
        file_rows.append([f.name, f.type or "—", dims, _fmt_bytes(f.size), status])

    # ── Store in session ──────────────────────────────────────────────────────
    await update_form_state(session_id, "creative", creative.model_dump())

    # ── Phase 3: async creative intelligence (deterministic + optional VLM) ──
    from config import config as _cfg
    if _cfg.USE_VLM_CREATIVE:
        from creative_intel.service import get_intel_by_ids

        analysis_ids = [f.analysisId for f in files if f.analysisId]
        verdicts = await get_intel_by_ids(session_id, analysis_ids)
        blocked = []
        for f in files:
            verdict = verdicts.get(f.analysisId)
            if not verdict:
                blocked.append(f"{f.name}: chưa có kết quả phân tích hợp lệ")
                continue
            if verdict.get("effective_status") not in {"auto_approved", "approved_override"}:
                reasons = "; ".join(verdict.get("review_reasons") or [])
                blocked.append(f"{f.name}: {reasons or verdict.get('status')}")
        if blocked:
            return AgentResponse(
                text="⚠ Creative cần được phân tích và duyệt trước khi sang bước Setup.",
                blocks=[{"type": "info", "text": "\n".join(f"- {item}" for item in blocked)}],
                meta=ResponseMeta(tool="creative_blocked", model="none", step=2),
            )
    await log_event(session_id, "handler", {"step": "creative", "files": len(files), "valid": valid_count})

    # ── Build blocks ──────────────────────────────────────────────────────────
    blocks = [
        {
            "type": "table",
            "title": f"🖼 Creative Files ({valid_count}/{len(files)} hợp lệ)",
            "columns": ["Tên file", "Format", "Kích thước", "Dung lượng", "Trạng thái"],
            "rows": file_rows,
        }
    ]

    if all_warnings:
        blocks.append({
            "type": "info",
            "text": f"⚠ {len(all_warnings)} vấn đề cần kiểm tra trước khi tiếp tục.",
        })

    blocks.append({
        "type": "info",
        "text": "✅ Anh/Chị tiếp tục chọn Audience ở bước tiếp theo!",
    })

    text = (
        f"✅ Đã nhận **{len(files)} file creative** ({valid_count} hợp lệ). "
        "Em sẽ dùng các file này để gán vào zone ở bước Setup."
    )

    return AgentResponse(
        text=text,
        blocks=blocks,
        meta=ResponseMeta(tool="creative_validate", model="none", step=1),
    )
