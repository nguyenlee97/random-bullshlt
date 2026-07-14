# Audience retrieval scoreboard

Evaluation date: 2026-07-14

Catalog: 310 segments

Set: 80 briefs (`brief_001`–`brief_080`)

| Candidate pipeline | Recall@50 | Must recall@K | MRR@K | nDCG@K | Exclusions | p50 |
|---|---:|---:|---:|---:|---:|---:|
| Raw hybrid | 0.785 | 0.713 | 0.563 | 0.464 | 12 | 0.036 s |
| Notes only | 0.782 | 0.671 | 0.585 | 0.470 | 17 | 0.029 s |
| Objective + notes | 0.784 | 0.673 | 0.580 | 0.475 | 18 | 0.036 s |
| Coverage-preserving rewrites | 0.848 | 0.696 | 0.680 | 0.509 | 10 | 1.420 s |
| **Raw + coverage-preserving rewrites** | **0.868** | **0.785** | **0.712** | **0.557** | **12** | **1.499 s** |
| **Raw + rewrites, 25-candidate pool** | **0.852** | **0.877** | **0.698** | **0.573** | **16** | **1.439 s** |
| Raw + Qwen reranker | 0.783 | 0.521 | 0.358 | 0.286 | 7 | 0.914 s |

`K=15` except the explicitly named 25-candidate row (`K=25`). Candidate exclusions measure what is present in the model's choice pool, not what is finally returned.

## End-to-end comparison

| Pipeline | Recall@15 | MRR@15 | Exclusions | Errors | Fallbacks | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Legacy 310-segment prompt | 0.791 | 0.769 | 3 | 1 | — | 35.91 s | 44.56 s |
| RAG, MiniMax selector, 15 candidates | 0.669 | 0.786 | 0 | 0 | 0 | 12.79 s | 18.55 s |
| **RAG, GPT-5.4 mini selector, 25 candidates + guard** | **0.831** | **0.848** | **0** | **0** | **0** | **4.11 s** | **5.96 s** |

The final RAG candidate improves recall by 4.0 percentage points and cuts p95 recommendation latency by 86.6% versus legacy. Stopping Qdrant produced one successful, explicitly counted legacy fallback; restarting Qdrant restored `rag_index: true` readiness.

## Verdict

- Candidate strategy: raw brief plus coverage-preserving query rewrites, 25 candidates, strict structured GPT-5.4 mini selection, candidate whitelist, and deterministic taxonomy guard.
- Qwen `qwen/qwen3-reranker-8b`: integrated but disabled. It causes a material ranking regression on this catalog.
- Retrieval infrastructure: ready. The versioned index contains all 310 live segments and matches the catalog fingerprint and embedding runtime metadata.
- Engineering gate: pass. The isolated local RAG candidate is staging-ready.
- Normal production flag: remains off until briefs 041–080 receive human label review and a staging soak/rehearsal is signed off.

## Release caveat

Briefs 041–080 are machine-authored and have not received the same explicit human sign-off as the original 40. These results are valid engineering diagnostics, but they are not sufficient by themselves to approve a production release.

Authoritative reports: `legacy-310.json`, `retrieval-raw-plus-rewrite-k25.json`, `rag-critic-k25-final.json`, and `rag-qdrant-fallback-smoke.json`.
