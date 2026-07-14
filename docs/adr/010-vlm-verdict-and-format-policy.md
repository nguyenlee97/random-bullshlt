# ADR 010 — VLM verdict policy and explicit creative format

**Date:** 2026-07-15
**Status:** Accepted

## Context

Gemma reliably extracts OCR, brand, safety, and brief fit from the available
demo creatives. It cannot reliably infer that a standalone narrow image is one
rail of a page takeover because the surrounding page context is absent.
Dimensions also cannot distinguish a side banner from a skin rail.

## Decision

- Use real bytes and Pillow for dimensions, format, aspect, animation, and
  minimum-size checks.
- Use `google/gemma-4-31b-it` for OCR, brand, subject, safety, confidence, and
  brief-match semantics.
- Require every VLM field in the function schema. Normalize only known,
  equivalent MaaS shapes (`safety: []`, `safety: false`, or `safety: "safe"`).
  Unknown or incomplete shapes fail closed to `needs_review`.
- Carry explicit `intendedFormat` metadata (`banner`, `skin`, or `video`) from
  the generator or operator. Assignment prefers this metadata over VLM layout
  inference. The VLM skin value remains an observable diagnostic.
- Any safety flag, confidence below 0.8, brief-match score at or below 2,
  deterministic failure, or VLM failure requires human review.

## Evidence

The optimized 20-image Gemma fixture run produced 95% structured success and,
on successful calls, 100% non-empty OCR, brand accuracy, safe-set safety
accuracy, and brief-match pass rate. Resizing only the VLM copy to 768px and
limiting output to 800 tokens reduced p50/p95 to 2.106/3.139 seconds. Raw VLM
skin accuracy was 73.7%, while explicit-format routing accuracy was 100%.

Qwen was rejected as primary: a five-case sample looked fast and correct, but
the full 20-image run produced only 40% schema-valid responses. The reports are
retained so the decision cannot be reversed based on a small lucky sample.

## Consequences

- Creative routing no longer depends on filenames.
- Uploaded skin assets require the operator to select `Skin / Background` if
  they do not originate from a generator carrying format metadata.
- A future page-context VLM evaluation may allow semantic layout inference to
  become authoritative, but only after a measured acceptance gate.
