# ViFoodVQA LLM-Assisted Verification

This folder contains the GPT-5.5-assisted verification workflow for the
currently provisional `train` and `validation` splits. It writes local artifacts
only; it does not update Supabase, Hugging Face exports, images, migrations, or
existing evaluation outputs.

## Setup

```powershell
cd ViFoodVQA/verification
pip install -e .[dev]
```

If you do not want to install the package, set `PYTHONPATH` for the current
PowerShell session:

```powershell
$env:PYTHONPATH = "src"
```

Required API environment variables for real GPT-5.5 runs:

```powershell
$env:OPENAI_COMPAT_API_KEY = "..."
$env:OPENAI_COMPAT_BASE_URL = "https://api.openai.com/v1"
```

The config also loads `.env` from `verification/.env` and `evaluation/.env`.

## Dataset And Image Metadata

The local Hugging Face-style JSONL files are the source for VQA rows:
`vqa_id`, `image_id`, image path, `qtype`, question, choices, answer,
rationale, and `triples_used`.

The JSONL export intentionally does not include `food_items` or `image_desc`.
Those fields live in the Supabase `image` table and should be queried by
`image_id` for production verification runs that need full image context.

Required Supabase environment variables for metadata enrichment:

```powershell
$env:SUPABASE_URL = "..."
$env:SUPABASE_KEY = "..."
```

The enrichment step should read `image_id`, `food_items`, and `image_desc`
only. It must not update Supabase verification fields.

Use `configs/verify_gpt55_hf_supabase.yaml` for the canonical 2026-05-15
`hf_dataset` snapshot plus Supabase `image` metadata enrichment.

Large local images are downsampled and JPEG-compressed before being embedded as
API data URLs. The default config keeps the long side at or below `1600` pixels
and the encoded image payload near `2 MB` or less to avoid request-body errors.

## Commands

Run calibration on the human-verified test split first:

```powershell
python -m vifood_verify.run calibrate --config configs/verify_gpt55.yaml --run-id gpt55_calibration
```

Run train/validation only after calibration metrics have been produced:

```powershell
python -m vifood_verify.run verify --config configs/verify_gpt55.yaml --run-id gpt55_train_val --calibration-run-dir outputs/gpt55_calibration
```

Run a small no-API smoke check:

```powershell
python -m vifood_verify.run all --config configs/verify_gpt55.yaml --run-id dry_run_smoke --limit 1 --dry-run --no-progress
```

Each run writes:

```text
outputs/<run_id>/
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

## Notes

- `calibrate` writes only `calibration_test.jsonl`.
- `verify` writes `train.jsonl` and `validation.jsonl`.
- `all` writes calibration and target split artifacts in one run.
- `--resume` skips rows already present in the target output JSONL.
- `--row-start N --row-end M` runs a 1-based inclusive global row range after
  split loading. For `verify`, the default order is all `train` rows followed by
  all `validation` rows. Use separate `--run-id` values when parallelizing.
- `--dry-run` never calls GPT and intentionally marks rows for review.
