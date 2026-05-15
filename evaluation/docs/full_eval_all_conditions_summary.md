# Full Evaluation Summary: All Models And Conditions

This document summarizes the revised ViFoodVQA evaluation results after the
2026-05-15 dropped-triple cascade cleanup.

Snapshot date: 2026-05-15.

## Incident Adjustment

The evaluated benchmark was revised from 1,410 to 1,401 samples. Supabase had
10 active `split=test` VQA rows whose `triples_used` referenced
`kg_triple_catalog.is_drop=true`; 9 of those rows appeared in every prediction
file and were removed before recomputing metrics. `vqa_id=9546` was absent from
prediction outputs because it was already outside the evaluated benchmark.

All 32 model-condition results below are from current prediction files under
`ViFoodVQA/evaluation/outputs`.

## Coverage Matrix

| Model | Current output conditions | Total available |
| --- | ---: | ---: |
| GPT-5.2 | 8 | 8/8 |
| GPT-5.5 | 8 | 8/8 |
| Qwen3-VL-2B | 8 | 8/8 |
| Phi-3.5-Vision-Instruct | 8 | 8/8 |
| **All models** | **32** | **32/32** |

## Overall Accuracy

`Parse failure` and `QType classifier` are reported when available from the
current evaluation outputs. No-KG conditions do not run query planning, so they
do not have qtype classifier metrics.

| Model | Condition | Test N | Accuracy | Parse failure | QType classifier |
| --- | --- | ---: | ---: | ---: | ---: |
| GPT-5.2 | `no_kg_0shot` | 1,401 | 88.22% | 0.50% | n/a |
| GPT-5.2 | `no_kg_1shot` | 1,401 | 88.65% | 0.36% | n/a |
| GPT-5.2 | `no_kg_2shot` | 1,401 | 86.30% | 1.36% | n/a |
| GPT-5.2 | `bm25` | 1,401 | 87.15% | 1.43% | 96.36% |
| GPT-5.2 | `vector_only` | 1,401 | 87.15% | 1.43% | 96.36% |
| GPT-5.2 | `graph_only` | 1,401 | 88.29% | 1.21% | 96.36% |
| GPT-5.2 | `hybrid` | 1,401 | 88.72% | 1.07% | 96.36% |
| GPT-5.2 | `oracle` | 1,401 | 95.29% | 0.64% | n/a |
| GPT-5.5 | `no_kg_0shot` | 1,401 | 90.65% | 0.00% | n/a |
| GPT-5.5 | `no_kg_1shot` | 1,401 | 90.86% | 0.00% | n/a |
| GPT-5.5 | `no_kg_2shot` | 1,401 | 90.94% | 0.00% | n/a |
| GPT-5.5 | `bm25` | 1,401 | 89.86% | 0.71% | 97.50% |
| GPT-5.5 | `vector_only` | 1,401 | 89.72% | 0.00% | 97.50% |
| GPT-5.5 | `graph_only` | 1,401 | 90.58% | 0.00% | 97.50% |
| GPT-5.5 | `hybrid` | 1,401 | 90.72% | 0.00% | 97.50% |
| GPT-5.5 | `oracle` | 1,401 | 95.50% | 0.93% | n/a |
| Qwen3-VL-2B | `no_kg_0shot` | 1,401 | 55.89% | 2.93% | n/a |
| Qwen3-VL-2B | `no_kg_1shot` | 1,401 | 54.25% | 0.93% | n/a |
| Qwen3-VL-2B | `no_kg_2shot` | 1,401 | 52.89% | 0.64% | n/a |
| Qwen3-VL-2B | `bm25` | 1,401 | 54.75% | 4.43% | 68.16% |
| Qwen3-VL-2B | `vector_only` | 1,401 | 55.60% | 4.64% | 68.16% |
| Qwen3-VL-2B | `graph_only` | 1,401 | 56.82% | 2.57% | 68.16% |
| Qwen3-VL-2B | `hybrid` | 1,401 | 54.32% | 1.93% | 68.90% |
| Qwen3-VL-2B | `oracle` | 1,401 | 82.87% | 1.36% | n/a |
| Phi-3.5-Vision-Instruct | `no_kg_0shot` | 1,401 | 35.76% | 0.86% | n/a |
| Phi-3.5-Vision-Instruct | `no_kg_1shot` | 1,401 | 24.84% | 16.77% | n/a |
| Phi-3.5-Vision-Instruct | `no_kg_2shot` | 1,401 | 27.34% | 8.64% | n/a |
| Phi-3.5-Vision-Instruct | `bm25` | 1,401 | 33.33% | 0.29% | 28.86% |
| Phi-3.5-Vision-Instruct | `vector_only` | 1,401 | 38.40% | 0.79% | 28.86% |
| Phi-3.5-Vision-Instruct | `graph_only` | 1,401 | 35.62% | 1.14% | 28.86% |
| Phi-3.5-Vision-Instruct | `hybrid` | 1,401 | 36.05% | 1.14% | 28.86% |
| Phi-3.5-Vision-Instruct | `oracle` | 1,401 | 64.24% | 2.07% | n/a |

## Retrieval Metrics

Retrieval metrics are available for KG and oracle conditions.

| Model | Condition | Test N | P@10 | R@10 | F1@10 |
| --- | --- | ---: | ---: | ---: | ---: |
| GPT-5.2 | `bm25` | 1,401 | 0.0147 | 0.1332 | 0.0263 |
| GPT-5.2 | `vector_only` | 1,401 | 0.0289 | 0.2358 | 0.0509 |
| GPT-5.2 | `graph_only` | 1,401 | 0.3321 | 0.4076 | 0.3558 |
| GPT-5.2 | `hybrid` | 1,401 | 0.3322 | 0.4079 | 0.3559 |
| GPT-5.2 | `oracle` | 1,401 | 1.0000 | 1.0000 | 1.0000 |
| GPT-5.5 | `bm25` | 1,401 | 0.0161 | 0.1486 | 0.0288 |
| GPT-5.5 | `vector_only` | 1,401 | 0.0298 | 0.2454 | 0.0525 |
| GPT-5.5 | `graph_only` | 1,401 | 0.3607 | 0.4882 | 0.3980 |
| GPT-5.5 | `hybrid` | 1,401 | 0.3613 | 0.4914 | 0.3990 |
| GPT-5.5 | `oracle` | 1,401 | 1.0000 | 1.0000 | 1.0000 |
| Qwen3-VL-2B | `bm25` | 1,401 | 0.0056 | 0.0494 | 0.0100 |
| Qwen3-VL-2B | `vector_only` | 1,401 | 0.0085 | 0.0678 | 0.0149 |
| Qwen3-VL-2B | `graph_only` | 1,401 | 0.0321 | 0.0389 | 0.0341 |
| Qwen3-VL-2B | `hybrid` | 1,401 | 0.0270 | 0.0325 | 0.0287 |
| Qwen3-VL-2B | `oracle` | 1,401 | 1.0000 | 1.0000 | 1.0000 |
| Phi-3.5-Vision-Instruct | `bm25` | 1,401 | 0.0031 | 0.0274 | 0.0055 |
| Phi-3.5-Vision-Instruct | `vector_only` | 1,401 | 0.0061 | 0.0496 | 0.0107 |
| Phi-3.5-Vision-Instruct | `graph_only` | 1,401 | 0.0153 | 0.0182 | 0.0160 |
| Phi-3.5-Vision-Instruct | `hybrid` | 1,401 | 0.0153 | 0.0182 | 0.0160 |
| Phi-3.5-Vision-Instruct | `oracle` | 1,401 | 1.0000 | 1.0000 | 1.0000 |

## Key Findings

- GPT-5.5 has the strongest overall current-run performance. Its best
  non-oracle condition is `no_kg_2shot` at 90.94%, while `hybrid` is close at
  90.72%.
- Oracle is the strongest condition for every model. The best overall result is
  GPT-5.5 `oracle` at 95.50%.
- For GPT models, graph-based retrieval remains much stronger than vector-only
  and BM25 by retrieval metrics. GPT-5.5 `hybrid` reaches the best non-oracle
  retrieval score with F1@10 = 0.3990.
- Open-weight baselines remain substantially weaker than GPT-5.2/GPT-5.5, but
  both show large gains when gold supporting triples are supplied.

## Notes And Limitations

- Qwen outputs use both `qwen3_vl_2b` and `qwen3_vl_2b_4bit` model identifiers
  across current output folders. This summary reports them under the single
  display label `Qwen3-VL-2B`.
- Classifier cache JSONL files were not pruned; qtype classifier accuracy is
  recomputed from the pruned prediction rows, not directly from raw cache size.
- Current no-KG conditions do not have qtype classifier metrics because query
  planning is only used by KG retrieval conditions.
