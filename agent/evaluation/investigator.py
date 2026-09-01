"""L2 investigation orchestration.

Builds a read-only evidence context, runs the playbook's probes, ranks root
causes deterministically, and returns an evidence bundle. This layer performs
no campaign, report, or catalog mutation of any kind — the only writes are the
investigation bundle attached to the incident and its timeline event.
"""
from __future__ import annotations

from datetime import datetime, timezone
import asyncio
import hashlib
import json

from evaluation.playbooks import probes_for, rank_hypotheses
from evaluation.probes import InvestigationContext, run_probes


BUNDLE_VERSION = "l2-investigation-v2"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _load_dataset(campaign_id: str) -> dict:
    from evaluation.service import report_request
    return await report_request("GET", f"/api/reports/internal/datasets/{campaign_id}")


async def _load_order(campaign_id: str) -> dict | None:
    try:
        from tools.order_api import fetch_order
        return await fetch_order(campaign_id)
    except Exception:
        # Evidence degrades to unavailable rather than failing the run.
        return None


async def _load_zone_map() -> dict[str, dict]:
    try:
        from tools.zone_catalog import get_zone_map
        return await get_zone_map() or {}
    except Exception:
        return {}


async def build_context(campaign_id: str, incident: dict, *, policy: dict | None = None,
                        dataset: dict | None = None) -> InvestigationContext:
    dataset = dataset if dataset is not None else await _load_dataset(campaign_id)
    baseline = (dataset.get("baseline") or {}) or {}
    active = (dataset.get("active") or {}) or {}
    order, zone_map = await asyncio.gather(_load_order(campaign_id), _load_zone_map())
    return InvestigationContext(
        campaign_id=campaign_id,
        scope=str(incident.get("scope") or "campaign"),
        issue_type=str(incident.get("issue_type") or ""),
        baseline_records=baseline.get("records") or [],
        active_records=active.get("records") or [],
        baseline_input=baseline.get("input") or {},
        order=order,
        zone_map=zone_map,
        policy=policy or {},
        evaluation_dates=(incident.get('evidence') or {}).get('dates') or [
            window['date'] for window in (incident.get('evidence') or {}).get('windows', []) if 'date' in window],
    )


def build_bundle(incident: dict, ctx: InvestigationContext, *, trigger: str,
                 dataset_revision: int | None = None,
                 policy_version: str = "") -> dict:
    """Pure bundle assembly, so ranking can be asserted without any I/O."""
    issue_type = str(incident.get("issue_type") or "")
    probe_ids = probes_for(issue_type)
    probe_results = run_probes(ctx, probe_ids) if probe_ids else {}
    ranking = rank_hypotheses(issue_type, probe_results)
    hypotheses = ranking["hypotheses"]
    top = hypotheses[0] if hypotheses else None
    assessment = ranking.get('assessment', 'unsupported')
    # Generic performance hypotheses require a real baseline comparison.
    if not ctx.baseline_records or not ctx.active_records:
        if issue_type != 'data_quality':
            top, assessment = None, 'insufficient_evidence'
    source_hash = hashlib.sha256(json.dumps({
        'baseline': ctx.baseline_records, 'active': ctx.active_records,
        'input': ctx.baseline_input, 'order': ctx.order, 'catalog': ctx.zone_map,
        'evaluation_dates': ctx.evaluation_dates,
    }, sort_keys=True, default=str).encode()).hexdigest()
    identity = f"{BUNDLE_VERSION}|{incident.get('incident_id')}|{dataset_revision}|{policy_version}|{source_hash}"
    return {
        'bundle_id': hashlib.sha256(identity.encode()).hexdigest(),
        'source_hash': source_hash,
        'evaluation_dates': ctx.evaluation_dates,
        'assessment': assessment,
        'ambiguous': ranking.get('ambiguous', False),
        'score_semantics': 'relative_rule_support_not_probability',
        "bundle_version": BUNDLE_VERSION,
        "incident_id": incident.get("incident_id"),
        "campaign_id": incident.get("campaign_id") or ctx.campaign_id,
        "issue_type": issue_type,
        "scope": ctx.scope,
        "supported": ranking["supported"],
        "title": ranking.get("title", ""),
        "trigger": trigger,
        "dataset_revision": dataset_revision,
        "policy_version": policy_version,
        "created_at": _now_iso(),
        "probes": [probe_results[key] for key in probe_ids if key in probe_results],
        "hypotheses": hypotheses,
        "gate": ranking["gate"],
        "top_hypothesis": top,
        "recovery_options": (top or {}).get("recovery_options", []) if assessment == 'supported_hypothesis' else [],
        'recovery_context': {
            'attempted_signal': 'recoveryAttempted' in ctx.signals(),
            'verification': 'not_verified',
            'note': 'Scenario signal alone does not prove an approved recovery or its outcome.',
        },
        "sources": {
            "order": bool(ctx.order),
            "zone_catalog": bool(ctx.zone_map),
            "baseline_records": bool(ctx.baseline_records),
            "active_records": bool(ctx.active_records),
            "baseline_input": bool(ctx.baseline_input),
        },
        "mutations": [],  # L2 is read-only by contract; kept explicit for audit.
    }


async def investigate_incident(campaign_id: str, incident: dict, *, trigger: str = "manual",
                               dataset: dict | None = None, policy: dict | None = None,
                               persist: bool = True) -> dict:
    """Run L2 for one incident and attach the evidence bundle."""
    from evaluation.store import attach_investigation, get_policy
    policy = policy or await get_policy(campaign_id)
    if not policy.get('enabled') or policy.get('level') not in {'L2', 'L3'}:
        raise PermissionError('L2 investigation requires enabled L2 or L3 policy')
    if incident.get('campaign_id') != campaign_id:
        raise PermissionError('incident campaign mismatch')
    if incident.get('state') in {'resolved', 'dismissed', 'false_positive'}:
        raise ValueError('incident is closed; run evaluation to detect recurrence')

    issue_type = str(incident.get("issue_type") or "")
    if not probes_for(issue_type):
        bundle = {
            "bundle_version": BUNDLE_VERSION,
            "incident_id": incident.get("incident_id"),
            "campaign_id": campaign_id,
            "issue_type": issue_type,
            "scope": incident.get("scope"),
            "supported": False,
            "trigger": trigger,
            "created_at": _now_iso(),
            "probes": [],
            "hypotheses": [],
            "gate": {"applied": False, "reasons": []},
            "top_hypothesis": None,
            "recovery_options": [],
            "note": f"Chưa có playbook L2 cho issue type “{issue_type}”.",
            "mutations": [],
        }
        # An unsupported playbook is not a completed investigation.
        return bundle

    dataset = dataset if dataset is not None else await _load_dataset(campaign_id)
    revision = int((dataset.get("state") or {}).get("activeRevision") or 1)
    if incident.get('dataset_revision') != revision:
        raise ValueError('Incident evidence is stale; run evaluation again')
    ctx = await build_context(campaign_id, incident, policy=policy, dataset=dataset)
    bundle = build_bundle(
        incident, ctx, trigger=trigger, dataset_revision=revision,
        policy_version=str((policy or {}).get("version") or ""),
    )
    if persist:
        current_dataset = await _load_dataset(campaign_id)
        if (current_dataset.get('state') or {}).get('activeRevision') != revision:
            raise ValueError('Dataset changed during investigation; run evaluation again')
        await attach_investigation(campaign_id, str(incident["incident_id"]), bundle)
    return bundle


async def investigate_incidents(campaign_id: str, incidents: list[dict], *,
                                trigger: str = "auto_l2", dataset: dict | None = None,
                                policy: dict | None = None) -> dict[str, dict]:
    """Investigate a batch, sharing one dataset read across all incidents."""
    if not incidents:
        return {}
    try:
        dataset = dataset if dataset is not None else await _load_dataset(campaign_id)
    except Exception:
        return {}
    bundles: dict[str, dict] = {}
    for incident in incidents:
        try:
            bundles[str(incident["incident_id"])] = await investigate_incident(
                campaign_id, incident, trigger=trigger, dataset=dataset, policy=policy,
            )
        except Exception:
            # One failed investigation must not block the others or the run.
            continue
    return bundles


def summarize_bundle(bundle: dict, *, max_hypotheses: int = 3) -> str:
    """Short Vietnamese summary for chat surfaces."""
    if bundle.get('mode') == 'multi_agent':
        return '\n'.join([
            bundle.get('summary') or 'Investigation chưa có kết luận.',
            f"{len(bundle.get('tasks') or {})} specialist · {len(bundle.get('probes') or [])} evidence.",
            'Kết luận dựa trên bằng chứng; chưa thực hiện recovery.',
        ])
    if not bundle.get("supported"):
        return bundle.get("note") or "Chưa có playbook điều tra cho loại sự cố này."
    lines: list[str] = []
    if bundle.get('assessment') == 'insufficient_evidence':
        lines.append('Chưa đủ bằng chứng để chọn nguyên nhân. Không đề xuất recovery.')
    elif bundle.get('ambiguous'):
        lines.append('Còn nhiều giả thuyết hợp lý; cần kiểm tra thêm trước khi xử lý.')
    lines.append('Điểm dưới đây là trọng số luật, không phải xác suất nguyên nhân.')
    for item in (bundle.get("hypotheses") or [])[:max_hypotheses]:
        lines.append(f"• {item.get('score_share', item['confidence'])} điểm — {item['label']}")
    gate = bundle.get("gate") or {}
    if gate.get("applied"):
        lines.append("→ Ưu tiên loại trừ lỗi dữ liệu/tracking trước.")
    anomalies = [
        probe for probe in (bundle.get("probes") or []) if probe.get("status") == "anomaly"
    ]
    if anomalies:
        lines.append("Bằng chứng: " + "; ".join(probe["summary"] for probe in anomalies[:3]))
    unavailable = [
        probe["probe_id"] for probe in (bundle.get("probes") or [])
        if probe.get("status") == "unavailable"
    ]
    if unavailable:
        lines.append(f"Chưa kiểm tra được: {', '.join(unavailable)}.")
    return "\n".join(lines) if lines else "Không tìm thấy nguyên nhân nổi bật."
