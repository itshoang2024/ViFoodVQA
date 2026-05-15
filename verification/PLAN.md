# LLM-Assisted Verification Plan

## Status

This plan is now implemented as a local verification workflow under
`ViFoodVQA/verification/`.

Implemented entry points:

- `python -m vifood_verify.run calibrate`: run GPT-5.5 verification on the
  human-verified `test` split.
- `python -m vifood_verify.run verify`: run GPT-5.5 verification on `train` and
  `validation` after calibration metrics exist.
- `python -m vifood_verify.run all`: run calibration plus target splits in one
  run.

The workflow writes local artifacts only. It does not update Supabase, Hugging
Face exports, images, migrations, or existing evaluation outputs.

## Goal

Use GPT-5.5 as an LLM-assisted verifier for the currently provisional `train`
and `validation` splits, while keeping the human-verified `test` split as the
benchmark source of truth and calibration set.

Rows accepted by this workflow should be reported as `LLM-assisted` or
`auto-verified`, not as `human-verified`.

## Scope And Baseline

Target splits:

| Split | Current role | Workflow action |
| --- | --- | --- |
| `train` | Provisional training data | Verify with GPT-5.5 after calibration |
| `validation` | Provisional validation data | Verify with GPT-5.5 after calibration |
| `test` | Human-verified benchmark data | Use for calibration and reporting |

Input source policy:

- Hugging Face-style JSONL split files are the row source for `vqa_id`,
  `image_id`, local image path, `qtype`, question, choices, answer, rationale,
  and `triples_used`.
- `food_items` and `image_desc` are image-level metadata from the Supabase
  `image` table, keyed by `image_id`. They are not part of the local
  Hugging Face export schema.
- Production verification should enrich JSONL rows from Supabase `image`
  before prompt construction when Supabase credentials are available.
- If Supabase enrichment is unavailable, the workflow may run from JSONL only,
  but reports must state that image metadata was unavailable and any resulting
  `empty_metadata`/low-confidence flags should be interpreted as a run-context
  limitation rather than an HF export defect.

Canonical split counts from the 2026-05-15 live snapshot after
`KG_TRIPLE_DROP_CASCADE_V1`:

| Split | Rows |
| --- | ---: |
| `train` | 5,930 |
| `validation` | 862 |
| `test` | 1,401 |

GPT-5.5 evaluation motivation:

| Condition | GPT-5.5 accuracy |
| --- | ---: |
| `no_kg_0shot` | 90.65% |
| `no_kg_2shot` | 90.94% |
| `oracle` | 95.50% |

These results justify GPT-5.5 as a verifier candidate, but answer accuracy is
not enough to prove verification quality. A model can answer a VQA row
correctly from visual priors, question wording, or weak distractors while
`triples_used` remains wrong or irrelevant. The workflow therefore preserves the
existing human rubric from `ViFoodVQA/docs/VERIFY_VQA_GUIDELINE.md`:

- `Q0`: Triple Used Validity
- `Q1`: Question Validity
- `Q2`: Choice Quality

## Implementation Map

| Path | Responsibility |
| --- | --- |
| `configs/verify_gpt55.yaml` | Default dataset path, GPT-5.5 model config, prompt version, audit settings, and risk qtypes. |
| `src/vifood_verify/run.py` | CLI orchestration for calibration, train/validation verification, metrics, queues, samples, and report generation. |
| `src/vifood_verify/prompts.py` | Three-pass prompt builders grounded in Q0/Q1/Q2. |
| `src/vifood_verify/verifier.py` | Calls the model, parses pass outputs, aggregates final `KEEP`, `DROP`, or `REVIEW`. |
| `src/vifood_verify/data.py` | Loads JSONL split rows, validates image/choice/triple fields, and filters dropped or empty-triple rows. |
| `src/vifood_verify/metadata.py` | Optional Supabase `image` metadata enrichment by `image_id` for `food_items` and `image_desc`, plus run-level metadata diagnostics. |
| `src/vifood_verify/model.py` | OpenAI-compatible GPT client plus `dry_run` model for local smoke tests. |
| `src/vifood_verify/metrics.py` | Overall and per-qtype calibration/decision metrics. |
| `src/vifood_verify/audit.py` | Human review queue and stratified audit sample builders. |
| `src/vifood_verify/report.py` | Markdown run report writer. |
| `tests/` | Parser, aggregation, metrics/audit, and dry-run CLI smoke tests. |

## Verification Protocol

Run GPT-5.5 with deterministic settings from `configs/verify_gpt55.yaml`:

- model: `gpt-5.5`
- temperature: `0`
- prompt version: `vqa_verify_gpt55_v1`
- required JSONL inputs: image, `image_id`, `qtype`, question, four choices,
  answer, and `triples_used`
- enriched Supabase `image` inputs when available: `food_items` and
  `image_desc`

Each row is checked by three passes:

1. **Pass 1 - VQA validity**: checks question-image fit, `qtype`, gold answer,
   and choice quality. Produces provisional `Q1` and `Q2`.
2. **Pass 2 - Triple validity**: checks every `triples_used` item in image/VQA
   context. Produces per-triple status and provisional `Q0`.
3. **Pass 3 - Adversarial review**: searches for reasons not to silently accept
   the row, including multiple correct choices, unsupported triples, ambiguous
   visual evidence, or pass disagreement.

Final labels:

| Label | Rule |
| --- | --- |
| `KEEP` | All passes accept, `Q0`, `Q1`, and `Q2` are all at least 3, and every core triple is `valid`. |
| `DROP` | `Q0 <= 2`, `Q1 <= 2`, `Q2 <= 2`, or a pass finds the row unusable for benchmarking. |
| `REVIEW` | Pass disagreement, low confidence, `needs_edit`, `unsure`, ambiguous image, parse failure, schema failure, or missing required input. |

`REVIEW` is intentionally conservative. It prevents ambiguous GPT judgments from
being silently promoted to final labels.

## Runbook

Install dependencies:

```powershell
cd ViFoodVQA/verification
pip install -e .[dev]
```

Or run without install in the current PowerShell session:

```powershell
$env:PYTHONPATH = "src"
```

Configure API access:

```powershell
$env:OPENAI_COMPAT_API_KEY = "..."
$env:OPENAI_COMPAT_BASE_URL = "https://api.openai.com/v1"
```

For production runs that use full image context, also provide Supabase access
so rows can be enriched from the `image` table:

```powershell
$env:SUPABASE_URL = "..."
$env:SUPABASE_KEY = "..."
```

The enrichment lookup should read only `image_id`, `food_items`, and
`image_desc` from Supabase `image`; it must not write verification decisions
back to Supabase.

Run calibration first:

```powershell
python -m vifood_verify.run calibrate --config configs/verify_gpt55.yaml --run-id gpt55_calibration
```

Run target splits only after calibration metrics exist:

```powershell
python -m vifood_verify.run verify --config configs/verify_gpt55.yaml --run-id gpt55_train_val --calibration-run-dir outputs/gpt55_calibration
```

Optional no-API smoke run:

```powershell
python -m vifood_verify.run all --config configs/verify_gpt55.yaml --run-id dry_run_smoke --limit 1 --dry-run --no-progress
```

Useful flags:

- `--resume`: skip rows already present in the target output JSONL.
- `--limit N`: run only the first `N` rows per selected split.
- `--sample-ids ...`: run specific `vqa_id` values.
- `--dry-run`: avoid GPT calls and intentionally route rows to `REVIEW`.
- `--skip-calibration-gate`: allow `verify` without a calibration directory,
  only for experiments.

## Calibration Gate

Before using train/validation labels, run calibration on all 1,401 `test` rows
and review:

- overall agreement with human labels;
- false KEEP rate;
- false DROP rate;
- `REVIEW` rate;
- decision and error distribution by `qtype`;
- high-risk disagreement examples, especially `Q0` disagreements.

Current local Hugging Face-style test exports may contain only human-kept test
rows, so false KEEP can be `n/a` unless dropped test rows are supplied. This
limitation must be stated in any report produced from local export artifacts.

## Artifact Contract

Run outputs are written under:

```text
ViFoodVQA/verification/outputs/<run_id>/
  config.json
  split_summary.json
  calibration_test.jsonl
  train.jsonl
  validation.jsonl
  review_queue.csv
  metrics_overall.csv
  metrics_by_qtype.csv
  audit_sample.csv
  report.md
```

Required row-level fields:

| Field | Type / values |
| --- | --- |
| `vqa_id` | source VQA id |
| `image_id` | source image id |
| `split` | `train`, `validation`, or `test` |
| `qtype` | source question type |
| `q0_score` | integer `1..4`, or null on parse/schema failure |
| `q1_score` | integer `1..4`, or null on parse/schema failure |
| `q2_score` | integer `1..4`, or null on parse/schema failure |
| `llm_decision` | `KEEP`, `DROP`, or `REVIEW` |
| `triple_reviews` | per-triple `valid`, `invalid`, `needs_edit`, or `unsure` |
| `confidence` | `high`, `medium`, or `low` |
| `failure_flags` | parse/schema/missing-input/disagreement flags |
| `rationale_short` | concise verifier explanation |
| `model` | e.g. `gpt-5.5` |
| `prompt_version` | e.g. `vqa_verify_gpt55_v1` |
| `run_id` | unique run id |
| `created_at` | ISO timestamp |

Additional diagnostic fields include raw pass outputs, parse statuses, raw
responses, latency, and inferred `human_decision` when available.

Recommended run-level diagnostics:

| Field | Meaning |
| --- | --- |
| `metadata_source` | `supabase_image`, `jsonl_embedded`, or `missing` |
| `metadata_missing_count` | Rows where `food_items` or `image_desc` could not be supplied |
| `metadata_lookup_failures` | Supabase lookup failures, if any |

## Storage Policy

Version 1 must not overwrite Supabase human verification fields.

Rules:

- write local artifacts under `ViFoodVQA/verification/outputs/<run_id>/`;
- do not modify `hf_dataset/`, image files, Supabase migrations, or existing
  evaluation outputs;
- do not set `is_checked=true` solely from GPT output;
- if Supabase writeback is added later, mark provenance with `LLM_GPT55_V1` in
  `verify_rule` or `verify_notes`;
- never report LLM-generated labels as human verification.

## Current Verification

Local implementation checks already run:

```text
python -m pytest
13 passed
```

A dry-run smoke command was also run on the real local dataset with `--limit 1`
and `--dry-run`; it generated the expected artifacts and did not call GPT. The
smoke output was deleted after inspection.

## Success Criteria

The workflow is ready for dataset use when:

- GPT-5.5 calibration on all test rows has been reported;
- `train` and `validation` have row-level LLM verification artifacts;
- every `REVIEW` row is separated into a human review queue;
- the stratified audit sample has been reviewed or explicitly scheduled;
- audited false KEEP risk is documented;
- public dataset claims distinguish human-verified `test` from LLM-assisted
  `train` and `validation`.
