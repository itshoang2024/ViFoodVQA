# LLM-Assisted Verification Plan

## Goal

Verify the currently unverified `train` and `validation` splits with GPT-5.5 as
an LLM-assisted verifier, while keeping the human-verified `test` split as the
benchmark source of truth and calibration set.

This plan treats GPT-5.5 as a high-confidence verification and triage tool, not
as a full replacement for human verification. Rows accepted by this workflow
should be reported as `LLM-assisted` or `auto-verified`, not as
`human-verified`.

## Scope And Baseline

Target splits:

| Split | Current role | Planned action |
| --- | --- | --- |
| `train` | Provisional training data | Run LLM-assisted verification |
| `validation` | Provisional validation data | Run LLM-assisted verification |
| `test` | Human-verified benchmark data | Use only for calibration and reporting |

Current canonical split counts from the 2026-04-29 live snapshot:

| Split | Rows |
| --- | ---: |
| `train` | 6,361 |
| `validation` | 914 |
| `test` | 1,410 |

The main motivation is that GPT-5.5 is the strongest evaluated model so far:

| Condition | GPT-5.5 accuracy |
| --- | ---: |
| `no_kg_0shot` | 90.57% |
| `no_kg_2shot` | 90.85% |
| `oracle` | 95.46% |

These results justify using GPT-5.5 as a verifier candidate, but answer
accuracy is not enough to prove verification quality. A model can answer a VQA
row correctly from visual priors, question wording, or weak distractors while
the underlying `triples_used` are still wrong or irrelevant. Therefore this
workflow must verify the same three criteria used by the existing human rubric:

- `Q0`: Triple Used Validity
- `Q1`: Question Validity
- `Q2`: Choice Quality

The source rubric remains `ViFoodVQA/docs/VERIFY_VQA_GUIDELINE.md`.

## Verification Protocol

Run GPT-5.5 with deterministic settings:

- model: `gpt-5.5`
- temperature: `0`
- prompt version: start with `vqa_verify_gpt55_v1`
- target rows: non-dropped rows from `train`, `validation`, and the calibration
  pass on `test`
- required inputs per row: image, `food_items`, `image_desc`, `qtype`,
  question, four choices, answer, and `triples_used`

Use three independent passes per VQA row:

1. **Pass 1 - VQA validity**: check whether the question matches the image,
   `qtype`, answer, and choices. Assign provisional `Q1` and `Q2`.
2. **Pass 2 - Triple validity**: review each `triples_used` item in the image
   context. Assign per-triple status: `valid`, `invalid`, `needs_edit`, or
   `unsure`. Assign provisional `Q0`.
3. **Pass 3 - Adversarial review**: actively search for reasons to reject the
   row, including multiple correct choices, unsupported KG facts, ambiguous
   image evidence, or a question that can be answered without the claimed
   triple.

Final labels:

| Label | Rule |
| --- | --- |
| `KEEP` | All passes agree; `Q0`, `Q1`, and `Q2` are all at least 3; no core triple is `invalid`, `needs_edit`, or `unsure`. |
| `DROP` | `Q0 <= 2`, or `Q1 <= 2`, or the answer/choices make the VQA unusable for benchmarking. |
| `REVIEW` | Any pass disagreement, low confidence, `Q2`-only issue, `needs_edit`, `unsure`, ambiguous image, parse failure, schema failure, or missing required input. |

`REVIEW` is deliberately conservative. It prevents ambiguous GPT judgments from
being silently promoted to final labels.

## Calibration Gate

Before applying labels to `train` or `validation`, run the same verifier on all
1,410 human-verified `test` rows and compare the LLM decision with the existing
human verification state.

Required calibration metrics:

- overall agreement with human labels
- false KEEP rate: GPT keeps rows that human verification dropped
- false DROP rate: GPT drops rows that human verification kept
- agreement and error distribution by `qtype`
- agreement and error distribution for each score field: `Q0`, `Q1`, `Q2`
- count and percentage of `REVIEW` rows
- examples of high-risk disagreements, especially `Q0` disagreements

Do not treat `train` or `validation` LLM labels as final until calibration
metrics are reported. If false KEEP is high on any `qtype`, route that qtype to
manual audit or tighten the prompt/rules before continuing.

## Audit Policy

Human work should be reduced, not removed completely.

Minimum audit after the LLM run:

- Review all `REVIEW` rows before they are treated as final.
- Audit a stratified sample from auto-`KEEP` and auto-`DROP` rows.
- Stratify by split, `qtype`, model confidence, and decision.
- Oversample high-risk qtypes such as `allergen_restrictions`,
  `dietary_restrictions`, `origin_locality`, and `substitution_rules`.
- Track human audit outcomes separately from LLM decisions.

Recommended acceptance gate:

- publish `LLM-assisted` counts only after the audited false KEEP rate is low
  enough for the intended use of the dataset;
- keep the test split human-verified in public benchmark claims;
- disclose the LLM-assisted process in reports, dataset cards, and release
  notes.

## Artifact Schema

The first implementation should write local artifacts before any database
writeback. Use JSONL for row-level outputs and CSV/Markdown for summaries.

Required row-level fields:

| Field | Type / values |
| --- | --- |
| `vqa_id` | source VQA id |
| `image_id` | source image id |
| `split` | `train`, `validation`, or `test` |
| `qtype` | source question type |
| `q0_score` | integer `1..4` |
| `q1_score` | integer `1..4` |
| `q2_score` | integer `1..4` |
| `llm_decision` | `KEEP`, `DROP`, or `REVIEW` |
| `triple_reviews` | per-triple status: `valid`, `invalid`, `needs_edit`, or `unsure` |
| `confidence` | `high`, `medium`, or `low` |
| `failure_flags` | parse/schema/missing-input/disagreement flags |
| `rationale_short` | concise verifier explanation |
| `model` | `gpt-5.5` |
| `prompt_version` | e.g. `vqa_verify_gpt55_v1` |
| `run_id` | unique run id |
| `created_at` | ISO timestamp |

Recommended output layout:

```text
ViFoodVQA/verification/outputs/<run_id>/
  config.json
  calibration_test.jsonl
  train.jsonl
  validation.jsonl
  review_queue.csv
  metrics_overall.csv
  metrics_by_qtype.csv
  audit_sample.csv
  report.md
```

## Storage Policy

Version 1 must not overwrite Supabase human verification fields.

Rules:

- write local artifacts under `ViFoodVQA/verification/outputs/<run_id>/`;
- do not modify `hf_dataset/`, image files, Supabase migrations, or existing
  evaluation outputs;
- do not set `is_checked=true` solely from GPT output;
- if later Supabase writeback is needed, mark provenance with
  `LLM_GPT55_V1` in `verify_rule` or `verify_notes`;
- never report LLM-generated labels as human verification.

## Reporting Requirements

Each verification run should produce a concise report containing:

- run metadata: `run_id`, date, model, prompt version, temperature, source data;
- source split counts and qtype distribution;
- decision distribution: `KEEP`, `DROP`, `REVIEW`;
- calibration metrics on the human-verified test split;
- audit sample design and audit outcomes;
- known limitations and qtypes requiring caution;
- exact policy used for whether a row is publishable, trainable, or still
  pending review.

## Success Criteria

The workflow is ready to use when:

- GPT-5.5 calibration on the test split has been reported;
- `train` and `validation` have row-level LLM verification artifacts;
- every `REVIEW` row is separated into a human review queue;
- audited false KEEP risk is documented;
- public dataset claims distinguish human-verified `test` from LLM-assisted
  `train` and `validation`.

