# LLM-Assisted Verification Tasks

## Goal

Produce a reliable GPT-5.5-assisted verification workflow for `train` and
`validation`, calibrated against the human-verified `test` split.

## Phase 1 - Inputs And Prompt

- [ ] Confirm source rows for `train`, `validation`, and `test` exclude dropped rows and empty `triples_used` rows. Verify by reporting split counts before any GPT call.
- [ ] Draft prompt `vqa_verify_gpt55_v1` using the existing Q0/Q1/Q2 rubric. Verify by checking the prompt requires scores, per-triple status, final label, confidence, and short rationale.

## Phase 2 - Calibration

- [ ] Run GPT-5.5 verification on all 1,410 human-verified `test` rows. Verify by producing `calibration_test.jsonl` with one valid JSON object per row.
- [ ] Compute agreement, false KEEP rate, false DROP rate, `REVIEW` rate, and per-qtype errors. Verify by producing `metrics_overall.csv` and `metrics_by_qtype.csv`.

## Phase 3 - Train And Validation Run

- [ ] Run the accepted verifier on `train` and `validation`. Verify by producing `train.jsonl` and `validation.jsonl` under `ViFoodVQA/verification/outputs/<run_id>/`.
- [ ] Generate the human review queue from all `REVIEW` rows and high-risk disagreements. Verify by producing `review_queue.csv` with split, qtype, reason, and priority.
- [ ] Draw a stratified audit sample from auto-`KEEP` and auto-`DROP` rows. Verify by producing `audit_sample.csv` covering split, qtype, decision, and confidence strata.

## Phase 4 - Reporting

- [ ] Write the run report with metadata, split counts, qtype distribution, decision distribution, calibration results, audit design, limitations, and release policy. Verify by producing `report.md`.

## Phase 5 - Verification

- [ ] Confirm no Supabase fields, Hugging Face export files, image files, migrations, or evaluation outputs were modified. Verify with `git status --short` and a focused diff/stat review.

