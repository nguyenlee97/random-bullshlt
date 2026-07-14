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

## Creative intelligence candidate

Evaluation date: 2026-07-15
Set: 20 real demo creatives across five brands and four placement formats.

| Model/pipeline | Schema success | OCR non-empty* | Brand* | Safe-set safety* | Brief match* | Raw skin* | Format routing | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Qwen full fixture | 40% | 100% | 100% | 100% | 100% | 62.5% | 100% | 4.43 s | 5.14 s |
| **Gemma optimized** | **95%** | **100%** | **100%** | **100%** | **100%** | 73.7% | **100%** | **2.11 s** | **3.14 s** |

`*` Semantic percentages are calculated on schema-valid responses. An invalid
or incomplete structured response fails closed to `needs_review`. Safety was
measured only on the safe demo set and does not yet establish unsafe-content
recall. Skin routing uses explicit `intendedFormat`; raw VLM skin prediction is
diagnostic because isolated rails lack page context.

### Safety and queue gates

| Gate | Result |
|---|---:|
| Unsafe direct-classification recall | 90% |
| Unsafe block-or-review recall | **100%** |
| Review-required escapes | **0** |
| OCR prompt-injection escapes | **0** |
| Safe auto-approve candidate rate | 100% |
| Safety fixture p95 | 5.88 s |
| HTTP queue terminal rate (20 files) | **100%** |
| HTTP queue within 20 seconds | **100%** |
| HTTP queue end-to-end p95 | **9.43 s** |
| Missing analysis IDs | **0** |

The video smoke accepted a real MP4, extracted 640x360 H.264 and two-second
duration metadata, and required manual review. The browser control proved that
review blocks Setup and that an operator reason creates a durable override
before the workflow can advance.

Verdict: Gemma remains primary. Qwen is rejected because its full-set schema
success regressed to 40% despite a strong five-case sample. **Local Gate 3
passes.** Authenticated override identity remains part of M4 before any
multi-user deployment.

Authoritative reports: `creative-v1-deterministic.json`,
`creative-v2-gemma-optimized.json`, `creative-v1-qwen.json`,
`creative-safety-gemma-v3.json`, and
`creative-http-queue-20-v3-concurrency6.json`. The single-worker
`creative-http-queue-20-v1.json` report is retained as before/after evidence.

## Full local campaign smoke

Evaluation date: 2026-07-15

| Gate | Result |
|---|---:|
| Complete flows | **3/3** |
| Duplicate retries returned original order | **3/3** |
| Unique orders across flows | **3/3** |
| Disposable artifacts cleaned up | **3/3** |
| End-to-end p95 | **6.08 s** |

Each flow used the live local catalog and RAG endpoint, committed a real source
segment, uploaded and analyzed a safe creative, assigned it to a real banner
placement, created an order through the server-side guard, retried with the
same idempotency key, fetched the result/report, and removed only its own test
artifacts. Authoritative report: `full-campaign-smoke.json`.
