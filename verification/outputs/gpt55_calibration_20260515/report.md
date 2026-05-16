# LLM-Assisted Verification Report: `gpt55_calibration_20260515`

## Metadata

- Created at: `2026-05-15T18:20:48.477307+00:00`
- Command: `calibrate`
- Model: `gpt-5.5`
- Prompt version: `vqa_verify_gpt55_v1`
- Temperature: `0`
- Max output tokens: `1800`

## Source Splits

| Split | Rows | Unique images | QTypes |
| --- | ---: | ---: | --- |
| `test` | 1401 | 248 | allergen_restrictions:78, cooking_technique:197, dietary_restrictions:150, dish_classification:170, flavor_profile:145, food_pairings:113, ingredient_category:262, ingredients:206, origin_locality:78, substitution_rules:2 |

## Image Metadata

- Requested source: `supabase_image`
- Effective source counts: `supabase_image:1401`
- Rows missing metadata: `0`
- Missing `food_items`: `0`
- Missing `image_desc`: `0`
- Lookup failures: `0`

## Decision Distribution

| Decision | Rows |
| --- | ---: |
| `KEEP` | 656 |
| `DROP` | 255 |
| `REVIEW` | 490 |

## Review And Audit

- Review queue rows: `745`
- Audit sample rows: `0`
- Human review is still required for every `REVIEW` row.
- Public claims must distinguish human-verified `test` from LLM-assisted `train` and `validation`.

## Known Limitations

- GPT answer accuracy is not equivalent to verification accuracy.
- Local Hugging Face-style test exports may contain only human-kept rows, so false KEEP can be `n/a` unless dropped test rows are provided.
- No Supabase field is updated by this workflow.
