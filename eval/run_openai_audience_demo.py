"""Production-facing OpenAI audience demo and edge-case evaluation.

This runner deliberately creates owned conversations locked to the OpenAI
campaign model. The legacy eval runner uses ownerless evaluator sessions, which
correctly preserve the GreenNode default and therefore cannot validate this
pipeline.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parent
GOLDEN = ROOT / "golden_set"
REPORTS = ROOT / "reports"
MODEL = "openai_gpt_5_4_mini"


def _load_catalog() -> tuple[dict[str, dict], dict[str, dict]]:
    raw = json.loads((GOLDEN / "catalog_full.json").read_text(encoding="utf-8"))
    rows = raw.get("data") or raw.get("attributes") or [] if isinstance(raw, dict) else raw
    by_mongo = {str(row["_id"]): row for row in rows if row.get("_id")}
    by_label = {
        str(row.get("fullLabel") or row.get("name")): row
        for row in rows
        if row.get("fullLabel") or row.get("name")
    }
    return by_mongo, by_label


CATALOG_BY_MONGO, CATALOG_BY_LABEL = _load_catalog()
CATALOG_IDS = {
    str(row.get("segmentId"))
    for row in CATALOG_BY_MONGO.values()
    if row.get("segmentId")
}


def _segment_id(label: str) -> str:
    row = CATALOG_BY_LABEL.get(label)
    if not row:
        raise KeyError(f"catalog label not found: {label}")
    return str(row["segmentId"])


def _golden(case_id: str, *, name: str, purpose: str) -> dict:
    case = json.loads((GOLDEN / f"{case_id}.json").read_text(encoding="utf-8"))
    labels = case["labels"]["audience"]

    def resolve(values: list[str]) -> list[str]:
        return [
            str(CATALOG_BY_MONGO[value]["segmentId"])
            for value in values
        ]

    return {
        "id": name,
        "source": case_id,
        "group": "demo",
        "purpose": purpose,
        "brief": case["brief"],
        "must_include": resolve(labels.get("must_include") or []),
        "acceptable": resolve(labels.get("acceptable") or []),
        "must_exclude": resolve(labels.get("must_exclude") or []),
        "require_direct": True,
    }


def _brief(
    brand: str,
    objective: str,
    kpi: str,
    notes: str,
    *,
    budget: int = 300,
) -> dict:
    return {
        "brand": brand,
        "objective": objective,
        "kpi": kpi,
        "budget": budget,
        "startDate": "2026-08-15",
        "endDate": "2026-09-30",
        "notes": notes,
    }


def cases() -> list[dict]:
    demos = [
        {
            "id": "demo_01_aquaguard_b2b_iot",
            "source": "recent_regression",
            "group": "demo",
            "purpose": "Catalog-gap B2B buyer intent versus broad consumer/business proxies.",
            "brief": _brief(
                "AquaGuard Industrial IoT",
                "consideration",
                "120 qualified demos with warehouse and facility operators",
                "Hệ thống cảm biến IoT giám sát rò rỉ nước cho kho vận và nhà xưởng. "
                "Người mua là quản lý cơ sở vật chất, vận hành kho và phụ trách kỹ thuật "
                "tại doanh nghiệp; không nhắm người mua sắm online hay người sửa nhà DIY.",
            ),
            "must_include": [],
            "acceptable": [_segment_id("Construction (industry)"),
                           _segment_id("Management (business & finance)")],
            "must_exclude": [_segment_id("Shops admins"),
                             _segment_id("Do it yourself (DIY)"),
                             _segment_id("Home improvement (home & garden)")],
            "direct_forbidden": [_segment_id("Construction (industry)"),
                                 _segment_id("Management (business & finance)")],
            "require_direct": False,
        },
        {
            "id": "demo_02_fertilizer_dealers",
            "source": "recent_regression",
            "group": "demo",
            "purpose": "Vietnamese agricultural B2B intent versus home-gardening proxies.",
            "brief": _brief(
                "Phân bón Nông Thịnh",
                "conversion",
                "500 đơn đăng ký làm đại lý phân phối",
                "Phân bón NPK bán sỉ cho đại lý vật tư nông nghiệp, hợp tác xã và trang "
                "trại thương mại. Không nhắm người trồng cây cảnh hoặc làm vườn tại nhà.",
            ),
            "must_include": [_segment_id("Agriculture (industry)")],
            "acceptable": [_segment_id("Gardening (outdoor activities)"),
                           _segment_id("Home and garden")],
            "must_exclude": [_segment_id("Shops admins")],
            "direct_forbidden": [_segment_id("Gardening (outdoor activities)"),
                                 _segment_id("Home and garden")],
            "require_direct": True,
        },
        {
            "id": "demo_03_mixigaming_controller",
            "source": "recent_regression",
            "group": "demo",
            "purpose": "Strong consumer gaming match with relevant genre expansion.",
            "brief": _brief(
                "Mixigaming Controller",
                "conversion",
                "4.000 tay cầm chơi game bán ra",
                "Tay cầm chơi game cho PC và console, hướng tới game thủ thường xuyên "
                "chơi action, FPS, racing, sports và game online. Không liên quan cờ bạc.",
            ),
            "must_include": [_segment_id("Video games (gaming)")],
            "acceptable": [_segment_id("Action games (video games)"),
                           _segment_id("First-person shooter games (video games)"),
                           _segment_id("Online games (video games)"),
                           _segment_id("Racing games (video game)"),
                           _segment_id("Sports games (video games)")],
            "must_exclude": [_segment_id("Gambling (gambling)"),
                             _segment_id("Casino games (gambling)")],
            "require_direct": True,
        },
        _golden(
            "brief_041",
            name="demo_04_digital_credit_card",
            purpose="Deep-catalog finance match and investment-banking near miss.",
        ),
        _golden(
            "brief_043",
            name="demo_05_sme_web_agency",
            purpose="B2B web services with product and business-buyer signals.",
        ),
        _golden(
            "brief_050",
            name="demo_06_expat_nfl_pub",
            purpose="Cross-type expat behavior plus specific sports interests.",
        ),
        _golden(
            "brief_052",
            name="demo_07_suv_pickup_dealer",
            purpose="Explicit product family and scooter exclusion.",
        ),
        _golden(
            "brief_053",
            name="demo_08_exotic_pet_store",
            purpose="Niche animal interests and tempting cat proxy exclusion.",
        ),
        _golden(
            "brief_066",
            name="demo_09_kids_english_parent_buyer",
            purpose="Parent buyer versus child user with an intentional catalog gap.",
        ),
        _golden(
            "brief_073",
            name="demo_10_aircraft_mro_b2b",
            purpose="Industrial aviation and engineering versus leisure air travel.",
        ),
    ]

    # The original golden label treated consumer "Aviation (air travel)" as a
    # direct MRO audience while excluding the nearly equivalent "Air travel".
    # Under the direct/adjacent contract this is a catalog-gap case: broad
    # Engineering/Management rows are optional proxies and leisure air-travel
    # interests are excluded.
    demos[9].update({
        "purpose": (
            "Industrial aviation catalog gap: keep Engineering/Management "
            "optional and reject leisure air-travel interests."
        ),
        "must_include": [],
        "acceptable": ["INT005", "INT008", "INT011", "INT016"],
        "must_exclude": ["INT004", "INT206"],
        "require_direct": False,
    })

    edge_prompt = _golden(
        "brief_080",
        name="edge_03_prompt_injection",
        purpose="Prompt injection in the brand must not change catalog constraints.",
    )
    edge_prompt["group"] = "edge"
    edge_primary = _golden(
        "brief_071",
        name="edge_05_primary_secondary_ev",
        purpose="Primary family-SUV buyer versus lower-priority technology audience.",
    )
    edge_primary["group"] = "edge"

    edges = [
        {
            **demos[1],
            "id": "edge_01_creative_milk_misdirection",
            "group": "edge",
            "source": "creative_only_variant",
            "purpose": "Creative milk imagery must not replace the fertilizer product.",
            "brief": _brief(
                "Phân bón Nông Thịnh",
                "conversion",
                "500 đơn đăng ký làm đại lý phân phối",
                "Sản phẩm thực tế là phân bón NPK bán sỉ cho đại lý vật tư nông nghiệp "
                "và trang trại thương mại. Ý tưởng hình ảnh quảng cáo dùng ly sữa trắng "
                "để ẩn dụ dinh dưỡng cho cây; sữa chỉ là hình ảnh sáng tạo, không phải "
                "sản phẩm và không phải audience. Không nhắm người làm vườn tại nhà.",
            ),
        },
        {
            **demos[0],
            "id": "edge_02_airport_backdrop",
            "group": "edge",
            "source": "location_creative_variant",
            "purpose": "Airport backdrop must not create travel intent.",
            "brief": _brief(
                "AquaGuard Industrial IoT",
                "awareness",
                "Reach 200 facility and warehouse decision makers",
                "Hệ thống cảm biến rò rỉ nước cho kho và nhà xưởng. Video quảng cáo quay "
                "tại một kho gần sân bay Tân Sơn Nhất để minh hoạ quy mô; sân bay chỉ là "
                "bối cảnh, sản phẩm không liên quan du lịch, hàng không hay vé máy bay.",
            ),
            "must_exclude": [
                *demos[0]["must_exclude"],
                _segment_id("Travel"),
                _segment_id("Aviation (air travel)"),
                _segment_id("Air travel (transportation)"),
                _segment_id("Travel (travel & tourism)"),
            ],
        },
        edge_prompt,
        {
            "id": "edge_04_vague_brief",
            "source": "ambiguity_probe",
            "group": "edge",
            "purpose": "A vague brief should not manufacture strong catalog matches.",
            "brief": _brief(
                "Nova",
                "awareness",
                "Tăng nhận diện",
                "Muốn tìm thêm khách hàng phù hợp cho sản phẩm mới.",
            ),
            "must_include": [],
            "acceptable": [],
            "must_exclude": [],
            "require_direct": False,
            "max_direct": 0,
        },
        edge_primary,
        {
            **demos[2],
            "id": "edge_06_mixigaming_paraphrase",
            "group": "edge",
            "source": "paraphrase_probe",
            "purpose": "English paraphrase should preserve core gaming meaning.",
            "brief": _brief(
                "Mixigaming Controller",
                "conversion",
                "Sell 4,000 controllers",
                "A PC and console gamepad for frequent players of shooters, racing, "
                "sports, action and multiplayer online titles. Gambling and casino "
                "players are explicitly outside the intended audience.",
            ),
            "compare_to": "demo_03_mixigaming_controller",
        },
        {
            **demos[2],
            "id": "edge_07_mixigaming_exact_repeat",
            "group": "edge",
            "source": "cache_consistency_probe",
            "purpose": "Exact repeat should be stable and use cached planning/reranking.",
            "compare_to": "demo_03_mixigaming_controller",
            "require_exact_match": True,
        },
    ]
    user_cases = [
        {
            "id": "user_01_zalo_kiki_car_ai",
            "source": "user_supplied_20260728",
            "group": "user",
            "purpose": (
                "A car AI assistant should surface the broad Automobiles "
                "coverage anchor without turning unrelated vehicle siblings "
                "into direct recommendations."
            ),
            "brief": {
                "brand": "Zalo",
                "objective": "Nhiều người biết đến và tải sản phẩm",
                "kpi": "Tăng nhận biết và lượt tải ứng dụng",
                "budget": 1000,
                "startDate": "2026-08-01",
                "endDate": "2026-08-03",
                "notes": (
                    "Quảng cáo ứng dụng AI Agent Kiki dành cho xe ô tô. "
                    "Mục tiêu là nhiều người biết đến và tải sản phẩm."
                ),
            },
            "must_include": ["INT219"],
            "acceptable": [
                "INT218", "INT221", "INT222", "INT223", "INT227", "INT286",
            ],
            "must_exclude": ["INT153", "INT154", "INT158"],
            "direct_forbidden": ["INT220", "INT224", "INT225", "INT226", "INT228"],
            "require_direct": True,
        },
        {
            "id": "user_02_banh_mi_o_to",
            "source": "user_supplied_20260728",
            "group": "user",
            "purpose": (
                "A food product for drivers should remain food-led; the "
                "driver context may support optional automotive expansion but "
                "must not replace the product audience."
            ),
            "brief": {
                "brand": "Bánh Mì Ô Tô",
                "objective": "Hướng tới tệp khách hàng phù hợp với sản phẩm",
                "kpi": "Tiếp cận khách hàng phù hợp và tăng chuyển đổi",
                "budget": 1000,
                "startDate": "2026-08-01",
                "endDate": "2026-08-03",
                "notes": (
                    "Bánh mì đóng hộp tiện lợi dùng cho tài xế. "
                    "Hướng tới tệp khách hàng phù hợp với sản phẩm."
                ),
            },
            "must_include": ["INT153", "INT158"],
            "acceptable": ["INT139", "INT154", "INT164"],
            "must_exclude": [],
            "direct_forbidden": [
                "INT218", "INT219", "INT220", "INT221", "INT222", "INT223",
                "INT224", "INT225", "INT226", "INT227", "INT228",
            ],
            "require_direct": True,
        },
    ]
    return demos + edges + user_cases


def _csrf_headers(client: httpx.AsyncClient) -> dict[str, str]:
    token = client.cookies.get("aa_csrf")
    if not token:
        raise RuntimeError("CSRF cookie was not issued")
    return {"X-CSRF-Token": token}


async def _mutation(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    **kwargs: Any,
) -> httpx.Response:
    headers = {**_csrf_headers(client), **kwargs.pop("headers", {})}
    response = await client.request(method, path, headers=headers, **kwargs)
    if response.status_code == 403 and response.cookies.get("aa_csrf"):
        headers["X-CSRF-Token"] = client.cookies.get("aa_csrf")
        response = await client.request(method, path, headers=headers, **kwargs)
    response.raise_for_status()
    return response


async def _recommend(
    client: httpx.AsyncClient,
    session_id: str,
) -> tuple[dict, float, list[dict]]:
    started = time.perf_counter()
    transient_retries = []
    for attempt in range(4):
        response = await client.get(
            "/api/agent/dmp-recommend",
            params={"session_id": session_id},
            timeout=200,
        )
        if response.status_code not in {429, 502, 503, 504}:
            response.raise_for_status()
            return (
                response.json(),
                time.perf_counter() - started,
                transient_retries,
            )
        transient_retries.append({
            "attempt": attempt + 1,
            "status_code": response.status_code,
            "elapsed_s": round(time.perf_counter() - started, 3),
        })
        retry_after = (
            max(float(response.headers.get("Retry-After", "8")), 8)
            if response.status_code == 429
            else 2
        )
        await asyncio.sleep(retry_after)
    raise RuntimeError(
        f"recommendation transient failure did not recover: "
        f"{transient_retries}"
    )


def _trace_event(logs: list[dict], event_type: str) -> dict:
    event = next((row for row in logs if row.get("type") == event_type), {})
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    return data or {}


def _compact_rec(row: dict) -> dict:
    return {
        "segmentId": row.get("segmentId") or row.get("_id"),
        "fullLabel": row.get("fullLabel") or row.get("name"),
        "tier": row.get("tier") or row.get("match_tier"),
        "relevance_score": row.get("relevance_score"),
        "reason": row.get("reason"),
        "matched_signals": row.get("matched_signals") or [],
        "missing_signals": row.get("missing_signals") or [],
        "limitation": row.get("limitation") or "",
    }


def _result(case: dict, conversation: dict, response: dict, latency: float,
            logs: list[dict], transient_retries: list[dict]) -> dict:
    direct = [_compact_rec(row) for row in response.get("recommendations") or []]
    adjacent = [
        _compact_rec(row)
        for row in response.get("adjacent_recommendations") or []
    ]
    direct_ids = {str(row.get("segmentId")) for row in direct}
    adjacent_ids = {str(row.get("segmentId")) for row in adjacent}
    all_ids = direct_ids | adjacent_ids
    must = set(case.get("must_include") or [])
    acceptable = set(case.get("acceptable") or [])
    excluded = set(case.get("must_exclude") or [])
    direct_forbidden = set(case.get("direct_forbidden") or [])
    unknown = sorted(value for value in all_ids if value not in CATALOG_IDS)
    exclusions = sorted(all_ids & excluded)
    forbidden_direct = sorted(direct_ids & direct_forbidden)
    missing_direct = sorted(must - direct_ids)
    trace = _trace_event(logs, "openai_audience_pipeline_trace")
    search_plan = _trace_event(logs, "openai_audience_search_plan")
    hard_failures = []
    if unknown:
        hard_failures.append("unknown_catalog_segment")
    if exclusions:
        hard_failures.append("explicit_exclusion_returned")
    if forbidden_direct:
        hard_failures.append("adjacent_proxy_promoted_to_direct")
    if case.get("require_direct") and must and not (must & direct_ids):
        hard_failures.append("no_expected_direct_match")
    if len(direct) > int(case.get("max_direct", 999)):
        hard_failures.append("too_many_direct_for_ambiguous_brief")
    return {
        "id": case["id"],
        "source": case.get("source"),
        "group": case["group"],
        "purpose": case["purpose"],
        "conversation_id": conversation["conversation_id"],
        "session_id": conversation["session_id"],
        "brief": case["brief"],
        "expected": {
            "must_include": sorted(must),
            "acceptable": sorted(acceptable),
            "must_exclude": sorted(excluded),
            "direct_forbidden": sorted(direct_forbidden),
        },
        "latency_s": round(latency, 3),
        "transient_retries": transient_retries,
        "direct": direct,
        "adjacent": adjacent,
        "metrics": {
            "direct_count": len(direct),
            "adjacent_count": len(adjacent),
            "direct_must_recall": (
                round(len(direct_ids & must) / len(must), 3) if must else None
            ),
            "all_tier_must_recall": (
                round(len(all_ids & must) / len(must), 3) if must else None
            ),
            "expected_direct_or_acceptable": sorted(
                direct_ids & (must | acceptable)
            ),
            "missing_expected_direct": missing_direct,
            "unknown": unknown,
            "exclusions_returned": exclusions,
            "forbidden_direct": forbidden_direct,
            "hard_failures": hard_failures,
        },
        "provider": response.get("provenance"),
        "rag": response.get("rag"),
        "search_plan": search_plan,
        "pipeline_trace": trace,
        "log_errors": [
            row for row in logs if row.get("type") in {"error", "warn"}
        ],
        "compare_to": case.get("compare_to"),
        "require_exact_match": bool(case.get("require_exact_match")),
    }


def _add_consistency(results: list[dict]) -> None:
    by_id = {row["id"]: row for row in results}
    for row in results:
        baseline_id = row.get("compare_to")
        if not baseline_id or baseline_id not in by_id:
            continue
        baseline = by_id[baseline_id]
        direct = {item["segmentId"] for item in row["direct"]}
        direct_base = {item["segmentId"] for item in baseline["direct"]}
        adjacent = {item["segmentId"] for item in row["adjacent"]}
        adjacent_base = {item["segmentId"] for item in baseline["adjacent"]}
        union = (direct | adjacent) | (direct_base | adjacent_base)
        overlap = (direct | adjacent) & (direct_base | adjacent_base)
        comparison = {
            "baseline": baseline_id,
            "direct_exact": direct == direct_base,
            "adjacent_exact": adjacent == adjacent_base,
            "tiered_jaccard": round(len(overlap) / len(union), 3) if union else 1.0,
        }
        row["consistency"] = comparison
        if row["require_exact_match"] and (
            not comparison["direct_exact"] or not comparison["adjacent_exact"]
        ):
            row["metrics"]["hard_failures"].append("exact_repeat_changed")


def _summary(results: list[dict]) -> dict:
    latencies = sorted(row["latency_s"] for row in results)
    must_recalls = [
        row["metrics"]["direct_must_recall"]
        for row in results
        if row["metrics"]["direct_must_recall"] is not None
    ]

    def percentile(values: list[float], value: float) -> float | None:
        if not values:
            return None
        index = max(0, min(len(values) - 1, round((len(values) - 1) * value)))
        return round(values[index], 3)

    return {
        "cases": len(results),
        "demo_cases": sum(row["group"] == "demo" for row in results),
        "edge_cases": sum(row["group"] == "edge" for row in results),
        "user_cases": sum(row["group"] == "user" for row in results),
        "cases_with_hard_failures": sum(
            bool(row["metrics"]["hard_failures"]) for row in results
        ),
        "cases_with_transient_retries": sum(
            bool(row.get("transient_retries")) for row in results
        ),
        "transient_retry_count": sum(
            len(row.get("transient_retries") or []) for row in results
        ),
        "hard_failures": {
            row["id"]: row["metrics"]["hard_failures"]
            for row in results
            if row["metrics"]["hard_failures"]
        },
        "unknown_catalog_segments": sum(
            len(row["metrics"]["unknown"]) for row in results
        ),
        "exclusions_returned": sum(
            len(row["metrics"]["exclusions_returned"]) for row in results
        ),
        "mean_direct_must_recall": (
            round(statistics.mean(must_recalls), 3) if must_recalls else None
        ),
        "p50_latency_s": percentile(latencies, 0.50),
        "p95_latency_s": percentile(latencies, 0.95),
        "max_latency_s": max(latencies, default=None),
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--agent-url",
        default="https://agent-api.pawgrammers.io.vn",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--case", default="")
    parser.add_argument("--pace-seconds", type=float, default=7.0)
    parser.add_argument(
        "--output",
        default="eval/reports/openai-audience-demo-20260728.json",
    )
    args = parser.parse_args()
    selected = cases()
    if args.case:
        selected = [row for row in selected if row["id"] == args.case]
    if args.limit:
        selected = selected[:args.limit]
    if not selected:
        raise SystemExit("no cases selected")

    results = []
    last_start = 0.0
    async with httpx.AsyncClient(
        base_url=args.agent_url,
        follow_redirects=True,
        timeout=210,
        headers={"User-Agent": "openai-audience-eval/1.0"},
    ) as client:
        bootstrap = await client.post("/api/agent/auth/anonymous")
        bootstrap.raise_for_status()
        for index, case in enumerate(selected, 1):
            delay = args.pace_seconds - (time.monotonic() - last_start)
            if delay > 0:
                await asyncio.sleep(delay)
            conversation = (
                await _mutation(
                    client,
                    "POST",
                    "/api/agent/conversations",
                    json={
                        "title": f"EVAL AUD {case['id']}",
                        "experience_mode": "guided",
                        "conversation_model": MODEL,
                    },
                )
            ).json()
            await _mutation(
                client,
                "POST",
                "/api/agent/commit-workspace",
                json={
                    "session_id": conversation["session_id"],
                    "field": "brief",
                    "value": case["brief"],
                    "actor": "openai_audience_eval",
                    "reason": case["purpose"],
                    "idempotency_key": f"aud-eval-{case['id']}",
                },
            )
            last_start = time.monotonic()
            try:
                response, latency, transient_retries = await _recommend(
                    client, conversation["session_id"],
                )
                log_response = await client.get(
                    f"/api/agent/logs/{conversation['session_id']}",
                    params={"limit": 1000},
                )
                log_response.raise_for_status()
                result = _result(
                    case,
                    conversation,
                    response,
                    latency,
                    log_response.json().get("logs") or [],
                    transient_retries,
                )
                results.append(result)
                print(
                    f"[{index:02d}/{len(selected):02d}] {case['id']}: "
                    f"direct={len(result['direct'])} "
                    f"adjacent={len(result['adjacent'])} "
                    f"fail={result['metrics']['hard_failures']} "
                    f"latency={result['latency_s']}s",
                    flush=True,
                )
            finally:
                await _mutation(
                    client,
                    "POST",
                    f"/api/agent/conversations/{conversation['conversation_id']}/archive",
                )

    _add_consistency(results)
    report = {
        "schema": "openai-audience-demo-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "agent_url": args.agent_url,
        "conversation_model": MODEL,
        "summary": _summary(results),
        "results": results,
    }
    output = Path(args.output)
    if not output.is_absolute():
        output = Path(__file__).resolve().parents[1] / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"report -> {output}")
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(asyncio.run(main()))
