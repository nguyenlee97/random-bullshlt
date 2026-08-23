"""Incident alerts and deterministic Zalo reply correlation.

Alerts add a separate recent-incident context only. They never select a
campaign and never replace an existing campaign ``pending_action``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import unicodedata

from config import config


_INCIDENT_RE = re.compile(r"\b(INC-[A-Z0-9]{4,12})\b", re.IGNORECASE)
_CHOICE_RE = re.compile(r"^\s*([1-4])(?:\s+|\s*[-:]|\s*$)", re.IGNORECASE)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def parse_incident_reply(message: str) -> tuple[str | None, int | None]:
    incident = _INCIDENT_RE.search(str(message or ""))
    choice = _CHOICE_RE.search(str(message or ""))
    return (
        incident.group(1).upper() if incident else None,
        int(choice.group(1)) if choice else None,
    )


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", str(value or "").lower())
    return " ".join(
        "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        .replace("đ", "d").split()
    )


async def _threads_for_campaign(campaign_id: str) -> list[dict]:
    from zalo_channel import _collections
    collections = await _collections()
    if collections is not None:
        import session
        ownership = await session._client[config.MONGODB_DB][
            "account_campaign_ownership"
        ].find_one({"order_id": campaign_id})
        if not ownership:
            return []
        owner_query = (
            {"user_id": ownership["owner_user_id"]}
            if ownership.get("owner_user_id")
            else {"user_id": None, "anonymous_id": ownership.get("anonymous_id")}
        )
        return await collections["threads"].find(owner_query).to_list(None)

    from campaign_ownership import _mem_campaigns
    from zalo_campaign_agent import _mem_threads
    ownership = _mem_campaigns.get(campaign_id)
    if not ownership:
        return []
    return [thread for thread in _mem_threads.values() if (
        ownership.get("owner_user_id") and thread.get("user_id") == ownership.get("owner_user_id")
    ) or (
        not ownership.get("owner_user_id")
        and thread.get("anonymous_id") == ownership.get("anonymous_id")
    )]


def _alert_text(campaign_id: str, incident: dict) -> str:
    evidence = incident.get("evidence") or {}
    metric = ""
    if "relative_drop" in evidence:
        metric = f" CTR giảm {round(float(evidence['relative_drop']) * 100)}%."
    elif evidence.get("windows"):
        ratio = evidence["windows"][-1].get("ratio")
        if ratio is not None:
            metric = f" Tỷ lệ gần nhất {round(float(ratio) * 100)}% so với baseline."
    return (
        f"⚠️ {incident['incident_id']} · {campaign_id}\n"
        f"{incident['title']} tại {incident['scope']}.{metric}\n\n"
        "Trả lời kèm mã incident:\n"
        f"1 {incident['incident_id']} — xem evidence\n"
        f"2 {incident['incident_id']} — điều tra\n"
        f"3 {incident['incident_id']} — chuẩn bị recovery\n"
        f"4 {incident['incident_id']} — dismiss"
    )


async def notify_incidents(campaign_id: str, incidents: list[dict], dataset_revision: int) -> int:
    from zalo_campaign_agent import _update_thread
    from zalo_worker import enqueue_text
    threads = await _threads_for_campaign(campaign_id)
    sent = 0
    for thread in threads:
        refs = list(thread.get("recent_incident_refs") or [])
        for incident in incidents:
            ref = {
                "incident_id": incident["incident_id"], "campaign_id": campaign_id,
                "dataset_revision": dataset_revision, "seen_at": _now(),
            }
            refs = [item for item in refs if item.get("incident_id") != incident["incident_id"]]
            refs.append(ref)
            await enqueue_text(
                thread=thread, text=_alert_text(campaign_id, incident),
                idempotency_key=f"evaluation-alert:{incident['incident_id']}:{dataset_revision}",
                category="evaluation_alert", incident_id=incident["incident_id"],
            )
            sent += 1
        # Deliberately update only this bounded namespace. active_campaign_id
        # and pending_action are not part of the write.
        thread = await _update_thread(thread, {"recent_incident_refs": refs[-10:]})
    return sent


async def _incident_from_reply(thread: dict, reply_to_message_id: str | None) -> str | None:
    if not reply_to_message_id:
        return None
    from zalo_channel import _collections
    collections = await _collections()
    if collections is None:
        return None
    outbound = await collections["outbound"].find_one({
        "thread_id": thread["thread_id"], "category": "evaluation_alert",
        "provider_message_id": reply_to_message_id,
    })
    return str((outbound or {}).get("incident_id") or "").upper() or None


async def handle_incident_reply(
    thread: dict, message: str, *, reply_to_message_id: str | None = None,
) -> tuple[str | None, dict]:
    incident_id, choice = parse_incident_reply(message)
    # Provider reply relation is stronger than free-text correlation.
    incident_id = await _incident_from_reply(thread, reply_to_message_id) or incident_id
    if not incident_id:
        return None, thread
    pending = thread.get("pending_action") or {}
    if pending.get("kind") == "incident_recovery" and pending.get("incident_id") == incident_id:
        expected = f"xac nhan {incident_id.lower()}"
        if _fold(message) != expected:
            return (
                f"Recovery {incident_id} đang chờ duyệt. Trả lời chính xác “Xác nhận {incident_id}” hoặc “Hủy” run.",
                thread,
            )
        from evaluation.service import report_request, run_evaluation
        from evaluation.store import transition_incident
        from zalo_campaign_agent import _update_thread
        campaign_id = pending["campaign_id"]
        await transition_incident(campaign_id, incident_id, "recovering", "Recovery confirmed from Zalo")
        try:
            scenario = await report_request(
                "POST", f"/api/reports/internal/scenarios/{campaign_id}/apply",
                {"presetId": "healthy_baseline", "seed": f"zalo-{incident_id}"},
            )
            await transition_incident(campaign_id, incident_id, "verifying", "Baseline restored; verification started")
            evaluation = await run_evaluation(campaign_id, trigger="zalo_recovery", force=True)
        except Exception as exc:
            await transition_incident(campaign_id, incident_id, "failed", str(exc)[:240])
            thread = await _update_thread(thread, {"pending_action": None})
            return f"Recovery {incident_id} thất bại: {str(exc)[:240]}", thread
        thread = await _update_thread(thread, {"pending_action": None})
        current = next((item for item in evaluation["incidents"] if item["incident_id"] == incident_id), None)
        state = (current or {}).get("state", "resolved")
        return (
            f"Đã chạy recovery {incident_id} bằng dataset revision {scenario['revision']} và verification. "
            f"Trạng thái hiện tại: {state}.", thread,
        )
    from evaluation.store import list_incidents, transition_incident
    from zalo_campaign_agent import _update_thread, owned_campaigns
    campaigns = await owned_campaigns(thread)
    owned_ids = {item["campaign_id"] for item in campaigns}
    matches = []
    for campaign_id in owned_ids:
        matches.extend([
            item for item in await list_incidents(campaign_id)
            if item["incident_id"].upper() == incident_id
        ])
    if len(matches) != 1:
        return f"Không tìm thấy {incident_id} trong các campaign bạn sở hữu.", thread
    incident = matches[0]
    campaign_id = incident["campaign_id"]
    if choice == 1 or choice is None:
        return (
            f"{incident_id}: {incident['title']}\nScope: {incident['scope']}\n"
            f"Severity: {incident['severity']}\nEvidence: {incident.get('evidence') or {}}\n"
            f"Đề xuất: {incident['recommended_action']}", thread,
        )
    if choice == 2:
        await transition_incident(campaign_id, incident_id, "investigating", "Zalo operator requested investigation")
        return f"Đã chuyển {incident_id} sang Investigating. Không có cấu hình campaign nào bị thay đổi.", thread
    if choice == 4:
        await transition_incident(campaign_id, incident_id, "dismissed", "Dismissed from Zalo")
        return f"Đã dismiss {incident_id}. Không có cấu hình campaign nào bị thay đổi.", thread
    if choice == 3:
        if thread.get("pending_action"):
            return (
                f"{incident_id} chưa tạo recovery vì đang có một thao tác khác chờ xác nhận. "
                "Hãy hoàn tất hoặc hủy thao tác đó trước.", thread,
            )
        nonce = incident_id.split("-", 1)[-1]
        pending = {
            "kind": "incident_recovery", "incident_id": incident_id,
            "campaign_id": campaign_id, "action": "restore_baseline",
            "nonce": nonce, "expires_at": _now() + timedelta(minutes=15),
        }
        thread = await _update_thread(thread, {"pending_action": pending})
        await transition_incident(campaign_id, incident_id, "awaiting_approval", "Recovery prepared from Zalo")
        return (
            f"Đã chuẩn bị recovery cho {incident_id}: khôi phục baseline report rồi chạy verification. "
            f"Trả lời chính xác “Xác nhận {incident_id}” để thực hiện, hoặc “Hủy”.",
            thread,
        )
    return f"Lựa chọn cho {incident_id} chưa hợp lệ. Dùng 1, 2, 3 hoặc 4 kèm mã incident.", thread
