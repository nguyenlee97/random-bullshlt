"""Build side-by-side HTML evidence reports for NP-6 ranking experiments."""
from __future__ import annotations

import argparse
from datetime import datetime
from html import escape
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


CSS = """
:root{color-scheme:light;--ink:#10233e;--muted:#65748b;--line:#dbe5f0;--blue:#1769e0;
--cyan:#0d99b5;--green:#14804a;--red:#c23b3b;--amber:#a56505;--paper:#fff;--bg:#f3f7fb}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
header{background:linear-gradient(130deg,#071a35,#0d3f79 58%,#0f7790);color:white;padding:38px max(24px,calc((100vw - 1440px)/2))}
header h1{margin:0 0 8px;font-size:30px}header p{max-width:1050px;margin:4px 0;color:#dbeafe}
main{max-width:1440px;margin:auto;padding:24px}.card{background:var(--paper);border:1px solid var(--line);
border-radius:16px;padding:18px;margin-bottom:18px;box-shadow:0 8px 30px rgba(15,50,90,.05)}
h2{font-size:20px;margin:0 0 12px}h3{font-size:15px;margin:0 0 8px}.muted{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.metric-grid{display:grid;
grid-template-columns:repeat(6,minmax(130px,1fr));gap:10px}.metric{border:1px solid var(--line);border-radius:12px;padding:12px;background:#f9fbfd}
.metric b{display:block;font-size:21px}.metric small{color:var(--muted)}table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{background:#edf4fb;position:sticky;top:0}
.pass{color:var(--green);font-weight:800}.fail{color:var(--red);font-weight:800}.warn{color:var(--amber);font-weight:700}
.variant{border:1px solid var(--line);border-radius:12px;padding:12px;background:#fbfdff;min-width:0}.variant.best{border-color:#7bd4a8;background:#f1fbf6}
.pill{display:inline-block;border-radius:999px;padding:2px 8px;font-size:11px;font-weight:800;background:#e8f1ff;color:#1556ad;margin:2px}
.rank-row{display:grid;grid-template-columns:27px 1fr;gap:7px;padding:5px 0;border-bottom:1px dashed #e5edf5}.rank-row:last-child{border:0}
.rank{width:24px;height:24px;border-radius:7px;background:#e8f1ff;display:grid;place-items:center;font-weight:900;color:#1556ad}
details.case{border:1px solid var(--line);background:white;border-radius:13px;margin:10px 0;overflow:hidden}
details.case summary{cursor:pointer;padding:13px 15px;font-weight:800;background:#f9fbfd;display:flex;gap:10px;align-items:center}
details.case[open] summary{border-bottom:1px solid var(--line)}.case-body{padding:14px}.brief{padding:10px 12px;background:#f5f8fb;border-left:4px solid var(--cyan);margin-bottom:12px}
.judgment-must_include{color:#0f7b45;font-weight:800}.judgment-acceptable{color:#1769e0}.judgment-must_exclude{color:#c23b3b;font-weight:900}
.legend{display:flex;gap:12px;flex-wrap:wrap}.callout{border-left:5px solid var(--blue);background:#edf5ff;padding:12px 14px;border-radius:8px}
code{background:#eaf0f6;padding:2px 5px;border-radius:5px}.footer{color:var(--muted);font-size:12px;padding:20px 0 40px}
@media(max-width:980px){.grid{grid-template-columns:1fr}.metric-grid{grid-template-columns:repeat(2,1fr)}main{padding:14px}header{padding:28px 18px}}
"""


def pct(value) -> str:
    return "—" if value is None else f"{float(value) * 100:.1f}%"


def num(value, digits=3) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}".rstrip("0").rstrip(".")


def shell(title: str, subtitle: str, body: str) -> str:
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>{CSS}</style></head><body>
<header><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></header>
<main>{body}<div class="footer">Generated {datetime.now().isoformat(timespec="seconds")} ·
Static evidence document; raw JSON remains under <code>eval/reports</code>.</div></main></body></html>"""


def placement_doc(report: dict, production_version: str) -> str:
    variants = report["variants"]
    by_id = {variant["id"]: variant for variant in variants}
    summaries = "".join(
        f"""<tr><td><b>{escape(variant['label'])}</b></td>
        <td>{pct(variant['summary']['top1_accuracy'])}</td>
        <td>{pct(variant['summary']['top3_accuracy'])}</td>
        <td>{pct(variant['summary']['semantic_top1_accuracy'])}</td>
        <td>{num(variant['summary']['mean_reciprocal_rank'])}</td>
        <td>{num(variant['summary']['p95_latency_s'])}s</td>
        <td>{variant['summary']['rerank_applied_cases']}/{variant['summary']['cases']}</td></tr>"""
        for variant in variants
    )
    cases = []
    for base in variants[0]["results"]:
        case_id = base["id"]
        rows = []
        for variant in variants:
            result = next(item for item in variant["results"] if item["id"] == case_id)
            topics = "".join(
                f"""<div class="rank-row"><span class="rank">{index}</span><div>
                <b>{escape(item['topic_id'])}</b><br><span class="muted">
                {escape(str(item.get('publisher') or ''))} · {escape(str(item.get('placement_id') or ''))}
                </span></div></div>"""
                for index, item in enumerate(result["top_topics"][:3], start=1)
            )
            status = (
                '<span class="pass">PASS · expected #1</span>'
                if result["top1_correct"]
                else f'<span class="fail">MISS · expected #{result["expected_topic_rank"] or "not in top 5"}</span>'
            )
            best = " best" if variant["id"] == "dense_bm25_nano" else ""
            rows.append(
                f"""<section class="variant{best}"><h3>{escape(variant['label'])}</h3>
                <p>{status} · {num(result['latency_s'])}s</p>{topics}</section>"""
            )
        brief = base["brief"]
        audience = ", ".join(
            str(item.get("fullLabel") or item.get("name") or item)
            for item in (base.get("audience") or [])
        )
        cases.append(
            f"""<details class="case"><summary><span class="pill">{escape(base['case_group'])}</span>
            {escape(case_id)} · expected <code>{escape(base['expected_topic'])}</code></summary>
            <div class="case-body"><div class="brief"><b>{escape(str(brief.get('brand') or ''))}</b> —
            {escape(str(brief.get('notes') or ''))}
            {f'<br><span class="muted">Audience: {escape(audience)}</span>' if audience else ''}</div>
            <div class="grid">{''.join(rows)}</div></div></details>"""
        )

    body = f"""
    <section class="card"><h2>Decision</h2><div class="callout">
    <b>Selected setup: Dense semantic + BM25 + GPT-5.4-nano topic reranking.</b>
    It reached 100% top-1 and top-3 accuracy across all {report['case_count']} cases, including
    direct topic, semantic-synonym, and audience-only cases. The cost is latency: p95
    {num(by_id['dense_bm25_nano']['summary']['p95_latency_s'])}s versus
    {num(by_id['deterministic_baseline']['summary']['p95_latency_s'])}s for the baseline.
    Deterministic performance, creative compatibility, and availability checks remain final guards.
    </div></section>
    <section class="card"><h2>Test design</h2>
    <p>Production build observed before the experiment: <code>{escape(production_version)}</code>.
    Catalog: {report['placement_count']} placements across {report['topic_count']} topic documents.
    The labeled suite contains 23 direct topic cases, 10 paraphrased semantic cases, and 10
    audience-only cases. Every configuration received the same catalog and campaign inputs.</p>
    <div class="legend"><span class="pill">Baseline: catalog keyword/context score + performance</span>
    <span class="pill">Hybrid: text-embedding-3-small + in-process BM25 + RRF</span>
    <span class="pill">Nano: bounded topic reorder; known IDs only</span></div></section>
    <section class="card"><h2>Aggregate quality</h2><div style="overflow:auto"><table><thead><tr>
    <th>Configuration</th><th>Top-1</th><th>Top-3</th><th>Semantic top-1</th><th>MRR</th><th>p95 latency</th><th>Rerank applied</th>
    </tr></thead><tbody>{summaries}</tbody></table></div>
    <p class="muted">Top-1 measures the expected topic at rank 1. Top-3 allows comparison alternatives.
    MRR rewards earlier expected-topic placement. Latency includes retrieval/reranking but not inventory API time.</p></section>
    <section class="card"><h2>Per-case output comparison</h2>
    <p class="muted">Open a row to compare the actual top three distinct topics side by side.</p>
    {''.join(cases)}</section>"""
    return shell(
        "NP-6 Placement Recommendation Experiment",
        "Deterministic baseline vs dense + BM25 vs dense + BM25 + GPT-5.4-nano",
        body,
    )


def audience_doc(retrieval: dict, nano: dict, production_version: str) -> str:
    variants = [*retrieval["variants"], nano["variant"]]
    by_id = {variant["id"]: variant for variant in variants}
    hybrid_recall = by_id["dense_bm25"]["summary"]["mean_retrieval_recall_at_50"]
    summaries = []
    for variant in variants:
        summary = variant["summary"]
        recall = (
            summary.get("mean_retrieval_recall_at_50")
            if variant["id"] != "dense_bm25_nano"
            else hybrid_recall
        )
        summaries.append(
            f"""<tr><td><b>{escape(variant['label'])}</b></td><td>{pct(recall)}</td>
            <td>{pct(summary['mean_must_recall_at_6'])}</td>
            <td>{num(summary['mean_mrr_at_6'])}</td><td>{num(summary['mean_ndcg_at_6'])}</td>
            <td>{summary['exclusion_violations_at_6']}</td>
            <td>{pct(summary['mean_must_recall_at_25'])}</td>
            <td>{num(summary['mean_ndcg_at_25'])}</td>
            <td>{summary['exclusion_violations_at_25']}</td>
            <td>{num(summary['p95_latency_s'])}s</td></tr>"""
        )

    case_ids = [result["id"] for result in variants[0]["results"]]
    cases = []
    for case_id in case_ids:
        base = next(item for item in variants[0]["results"] if item["id"] == case_id)
        columns = []
        for variant in variants:
            result = next(item for item in variant["results"] if item["id"] == case_id)
            items = "".join(
                f"""<div class="rank-row"><span class="rank">{item['rank']}</span><div>
                <b class="judgment-{escape(item['judgment'])}">{escape(str(item['label']))}</b><br>
                <span class="muted">{escape(str(item.get('category') or ''))} · {escape(item['judgment'])}</span>
                </div></div>"""
                for item in result["top_segments"][:6]
            )
            summary = result["at_6"]
            status = (
                f"must recall {pct(summary['must_recall'])} · nDCG {num(summary['ndcg'])} · "
                f"excluded {len(summary['exclusion_violations'])}"
            )
            best = " best" if variant["id"] == "dense_bm25_nano" else ""
            columns.append(
                f"""<section class="variant{best}"><h3>{escape(variant['label'])}</h3>
                <p class="muted">{status} · {num(result['latency_s']['total'])}s</p>{items}</section>"""
            )
        expected = base["expected"]
        cases.append(
            f"""<details class="case"><summary>{escape(case_id)} ·
            <span class="pill">{escape(', '.join(base.get('tags') or ['general']))}</span></summary>
            <div class="case-body"><div class="brief"><b>{escape(str(base['brief'].get('brand') or ''))}</b> —
            {escape(str(base['brief'].get('notes') or ''))}<br>
            <span class="pass">Must:</span> {escape(', '.join(expected['must_include']) or '—')}<br>
            <span class="fail">Exclude:</span> {escape(', '.join(expected['must_exclude']) or '—')}</div>
            <div class="grid">{''.join(columns)}</div></div></details>"""
        )

    selected = by_id["dense_bm25_nano"]["summary"]
    body = f"""
    <section class="card"><h2>Decision</h2><div class="callout">
    <b>Selected candidate pipeline: dense semantic + BM25 retrieval followed by bounded GPT-5.4-nano reranking.</b>
    On 80 briefs, must-include recall@6 increased from
    {pct(by_id['dense_bm25']['summary']['mean_must_recall_at_6'])} to
    {pct(selected['mean_must_recall_at_6'])}; nDCG@6 increased from
    {num(by_id['dense_bm25']['summary']['mean_ndcg_at_6'])} to
    {num(selected['mean_ndcg_at_6'])}. p95 candidate-stage latency is
    {num(selected['p95_latency_s'])}s. Deterministic negative-intent guards and the catalog-only
    final selector remain mandatory; this experiment does not alter unique-reach arithmetic.
    </div></section>
    <section class="card"><h2>Test design and boundary</h2>
    <p>Production build observed before the experiment: <code>{escape(production_version)}</code>.
    The frozen golden set contains 80 Vietnamese/English briefs and a 310-segment catalog snapshot.
    These measurements isolate candidate ordering before the final Copilot/Autopilot selector:
    BM25-only, hybrid dense+BM25 RRF, then the same hybrid pool reordered by nano.</p>
    <p class="warn">Important: retrieval quality is not audience reach. NP-2's canonical reach range,
    confidence, universe cap, ownership, confirmation, and order contracts are unchanged.</p></section>
    <section class="card"><h2>Aggregate quality</h2><div style="overflow:auto"><table><thead><tr>
    <th>Configuration</th><th>Recall@50</th><th>Must recall@6</th><th>MRR@6</th><th>nDCG@6</th>
    <th>Excluded@6</th><th>Must recall@25</th><th>nDCG@25</th><th>Excluded@25</th><th>p95 latency</th>
    </tr></thead><tbody>{''.join(summaries)}</tbody></table></div>
    <p class="muted">Must recall measures labeled required segments recovered. nDCG rewards required
    segments above acceptable ones. Excluded counts are golden-set contraindications appearing in
    the raw ranked list; production still applies deterministic guards and a candidate-ID-constrained selector.</p></section>
    <section class="card"><h2>Per-case output comparison</h2>
    <div class="legend"><span class="judgment-must_include">green = must include</span>
    <span class="judgment-acceptable">blue = acceptable</span>
    <span class="judgment-must_exclude">red = must exclude</span>
    <span class="muted">gray = unlabeled</span></div>{''.join(cases)}</section>"""
    return shell(
        "NP-6 Audience Recommendation Experiment",
        "BM25 baseline vs dense + BM25 vs dense + BM25 + GPT-5.4-nano",
        body,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--placement",
        default="eval/reports/np6-placement-matrix-20260727.json",
    )
    parser.add_argument(
        "--audience-retrieval",
        default="eval/reports/np6-audience-retrieval-matrix-local.json",
    )
    parser.add_argument(
        "--audience-nano",
        default="eval/reports/np6-audience-nano-matrix-20260727.json",
    )
    parser.add_argument("--production-version", default="2026-07-27.1")
    args = parser.parse_args()

    placement = json.loads((ROOT / args.placement).read_text(encoding="utf-8"))
    retrieval = json.loads(
        (ROOT / args.audience_retrieval).read_text(encoding="utf-8")
    )
    nano = json.loads((ROOT / args.audience_nano).read_text(encoding="utf-8"))

    placement_path = (
        ROOT / "docs/next-hackathon/57-np6-placement-ranking-experiment.html"
    )
    audience_path = (
        ROOT / "docs/next-hackathon/58-np6-audience-ranking-experiment.html"
    )
    placement_path.write_text(
        placement_doc(placement, args.production_version),
        encoding="utf-8",
    )
    audience_path.write_text(
        audience_doc(retrieval, nano, args.production_version),
        encoding="utf-8",
    )
    print(placement_path)
    print(audience_path)


if __name__ == "__main__":
    main()

