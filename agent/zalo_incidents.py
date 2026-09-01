"""Incident alerts and deterministic Zalo reply correlation.

Alerts add a separate recent-incident context only. They never select a
campaign and never replace an existing campaign ``pending_action``.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
import unicodedata

from config import config


_INCIDENT_RE = re.compile(r"\b(INC-[A-Z0-9]{4,12})\b", re.IGNORECASE)
_CHOICE_RE = re.compile(r"^\s*([1-4])(?:\s*(?:[-:]\s*)?INC-[A-Z0-9]{4,12})?\s*$", re.IGNORECASE)


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
    diagnosis = ""
    investigation = incident.get("investigation") or {}
    top = investigation.get("top_hypothesis") or {}
    if investigation.get('mode') == 'multi_agent':
        label = 'chưa chốt nguyên nhân' if investigation.get('cause_status') != 'supported_hypothesis' else 'giả thuyết có evidence, chưa chứng minh nhân quả'
        diagnosis = '\nL2 (' + label + '): ' + str(investigation.get('summary') or 'Chưa có kết luận.')[:500]
        if investigation.get('limitations'):
            diagnosis += '\nGiới hạn: ' + str(investigation['limitations'][0])[:220]
    elif investigation.get('assessment') == 'insufficient_evidence':
        diagnosis = '\nL2: chưa đủ bằng chứng để chọn nguyên nhân.'
    elif top:
        diagnosis = f"\nGiả thuyết cần kiểm tra: {top['label']}."
        if investigation.get('ambiguous'):
            diagnosis += ' Còn nhiều khả năng; chưa kết luận nguyên nhân.'
    return (
        f"⚠️ {incident['incident_id']} · {campaign_id}\n"
        f"{incident['title']} tại {incident['scope']}.{metric}{diagnosis}\n\n"
        "Trả lời kèm mã incident:\n"
        f"1 {incident['incident_id']} — xem evidence\n"
        f"2 {incident['incident_id']} — điều tra\n"
        f"3 {incident['incident_id']} — trạng thái recovery (chưa mở)\n"
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
                idempotency_key=f"evaluation-alert:{incident['incident_id']}:{dataset_revision}:{(incident.get('investigation') or {}).get('bundle_id', 'l1')}",
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
    external_event_id: str | None = None,
) -> tuple[str | None, dict]:
    incident_id, choice = parse_incident_reply(message)
    explicit_ids = {value.upper() for value in _INCIDENT_RE.findall(message)}
    if len(explicit_ids) > 1:
        return 'Tin nhắn có nhiều mã incident. Hãy gửi một mã duy nhất; chưa thực hiện thao tác nào.', thread
    # Explicit switching back to common campaign flows never inherits an alert.
    if not incident_id and (_fold(message) in {'faq', 'xem report', 'xem bao cao', 'xac nhan', 'tao campaign moi'}
                           or _fold(message).startswith(('tao campaign ', 'tao chien dich '))):
        return None, thread
    reply_id = await _incident_from_reply(thread, reply_to_message_id)
    if reply_id and incident_id and reply_id != incident_id:
        return 'Mã incident và tin nhắn được trả lời không khớp. Hãy gửi lại đúng một mã, không reply tin cũ; chưa thực hiện thao tác nào.', thread
    incident_id = reply_id or incident_id
    if not incident_id:
        return None, thread
    pending = thread.get("pending_action") or {}
    if pending.get("kind") == "incident_recovery":
        from zalo_campaign_agent import _update_thread
        thread = await _update_thread(thread, {"pending_action": None})
        return "Recovery cũ đã được hủy: L3 chưa có executor an toàn. Không có dữ liệu nào bị thay đổi.", thread
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
    question = _INCIDENT_RE.sub('', message).strip(' :-')
    if choice is None and question and _fold(question) not in {'cho toi xem', 'xem', 'xem evidence'}:
        from evaluation.questions import answer, QuestionError
        import hashlib
        bundle = incident.get('investigation') or {}
        request_id = hashlib.sha256(str(external_event_id or (message + str(bundle.get('bundle_id')))).encode()).hexdigest()
        try:
            result = await answer(campaign_id, incident_id, question=question, request_id=request_id,
                                  expected_revision=incident.get('dataset_revision'),
                                  expected_bundle_id=bundle.get('bundle_id'),
                                  channel='zalo:' + thread['thread_id'])
            citations = '\n'.join(f"• {c['evidence_id']} — {c['probe_id']}" for c in result['citations'][:3])
            excerpt = result['answer'][:1000]
            if result.get('limitations'):
                excerpt += '\nGiới hạn: ' + str(result['limitations'][0])[:220]
            more = '\nBản đầy đủ và nguồn evidence được lưu trong hỏi đáp trên web.'
            return (f"{incident_id} · revision {result['dataset_revision']}\n{excerpt}\n"
                    f"{citations}{more}\n{result['notice']}\nHỏi tiếp: gửi câu hỏi kèm {incident_id}.", thread)
        except QuestionError as exc:
            return f'{incident_id}: {exc}', thread
        except Exception:
            return f'{incident_id}: Chưa trả lời được câu hỏi. Không có thao tác campaign nào được thực hiện.', thread
    if choice == 1 or choice is None:
        return (
            f"{incident_id}: {incident['title']}\nScope: {incident['scope']}\n"
            f"Severity: {incident['severity']}\nEvidence: {incident.get('evidence') or {}}\n"
            f"Đề xuất: {incident['recommended_action']}", thread,
        )
    if choice == 2:
        from evaluation.investigator import investigate_incident, summarize_bundle
        from evaluation.store import get_policy
        try:
            policy = await get_policy(campaign_id)
            if config.EVALUATION_MULTI_AGENT_ENABLED:
                from evaluation.investigation_jobs import enqueue
                job = await enqueue(campaign_id, incident, policy, trigger='zalo')
                return (f"🔍 {incident_id} — investigation {job['job_id']}: {job['status']}. "
                        "Specialist chạy nền; kết quả sẽ được cập nhật qua Zalo. "
                        "Không thay đổi campaign hoặc yêu cầu duyệt hiện tại.", thread)
            bundle = await investigate_incident(
                campaign_id, incident, trigger="zalo", policy=policy,
            )
        except Exception as exc:
            # Investigation is read-only, so a failure leaves the incident
            # exactly as it was rather than parking it in a misleading state.
            return (
                f"Chưa chạy được điều tra cho {incident_id}: {str(exc)[:160]}. "
                "Không có cấu hình campaign nào bị thay đổi.", thread,
            )
        if not bundle.get("supported"):
            return (
                f"{incident_id}: {bundle.get('note') or 'Chưa có playbook điều tra.'} "
                "Chưa chạy điều tra. Không có cấu hình campaign nào bị thay đổi.",
                thread,
            )
        return (
            f"🔍 {incident_id} — kết quả điều tra (chỉ đọc)\n"
            f"{summarize_bundle(bundle)}\n\n"
             "L3 chưa mở; kết quả này không thực thi recovery. "
            "Không có cấu hình campaign nào bị thay đổi.", thread,
        )
    if choice == 4:
        await transition_incident(campaign_id, incident_id, "dismissed", "Dismissed from Zalo")
        return f"Đã dismiss {incident_id}. Không có cấu hình campaign nào bị thay đổi.", thread
    if choice == 3:
        return (
            f"{incident_id}: L3 chưa được mở. Hãy xem kết quả L2; "
            "khôi phục dữ liệu test được thực hiện riêng trong Scenario Lab. Không có dữ liệu nào bị thay đổi.",
            thread,
        )
    return f"Lựa chọn cho {incident_id} chưa hợp lệ. Dùng 1, 2, 3 hoặc 4 kèm mã incident.", thread
