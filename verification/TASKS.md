# LLM-Assisted Verification Tasks

## Goal

Track implementation and execution work for GPT-5.5-assisted verification of
`train` and `validation`, calibrated against the human-verified `test` split.

## Implementation

- [x] Create the verification package, config, README, and CLI entry points. Verify with `python -m vifood_verify.run --help`.
- [x] Implement source row loading and filtering for non-dropped rows with non-empty `triples_used`. Verify with loader validation and dry-run split summaries.
- [x] Implement optional Supabase `image` metadata enrichment by `image_id` for `food_items` and `image_desc`. Verify with a dry run that reports `metadata_source=supabase_image` and has no `empty_metadata` flags caused only by the HF JSONL schema.
- [x] Implement prompt `vqa_verify_gpt55_v1` with Q0/Q1/Q2, per-triple status, final label, confidence, and short rationale. Verify in `src/vifood_verify/prompts.py`.
- [x] Implement three-pass aggregation into `KEEP`, `DROP`, or `REVIEW`. Verify with `tests/test_verifier.py`.
- [x] Implement calibration metrics, review queue, audit sample, and report generation. Verify with `tests/test_metrics_audit.py` and dry-run artifacts.
- [x] Add parser and CLI smoke tests. Verify with `python -m pytest` from `ViFoodVQA/verification`.

## Execution

- [ ] Run full GPT-5.5 calibration on all 1,401 `test` rows after metadata enrichment is available, or explicitly document that the run used JSONL-only metadata. Verify by producing `outputs/<run_id>/calibration_test.jsonl`, `metrics_overall.csv`, `metrics_by_qtype.csv`, and `report.md`.
- [ ] Review calibration results and decide whether false DROP / false KEEP / `REVIEW` rates are acceptable. Verify by recording the decision in the run report or a follow-up note.
- [ ] Run GPT-5.5 verification on `train` and `validation` with `--calibration-run-dir`. Verify by producing `train.jsonl`, `validation.jsonl`, `review_queue.csv`, and `audit_sample.csv`.
- [ ] Complete human audit for all `REVIEW` rows and the stratified audit sample before public release. Verify by documenting audit outcomes and confirming no Supabase fields, Hugging Face exports, images, migrations, or evaluation outputs were modified unintentionally.
