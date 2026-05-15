# Tổng Kết Full Evaluation GPT-5.2 và GPT-5.5

Báo cáo này được cập nhật sau sự cố VQA dùng triple đã bị drop. Incident
snapshot nằm tại `ViFoodVQA/verification/outputs/kg_triple_drop_cascade_20260515/`.

Ngày chốt số liệu: 2026-05-15.

## Điều Chỉnh Benchmark

- Supabase đã soft-drop 493 active VQA rows theo rule `KG_TRIPLE_DROP_CASCADE_V1`.
- Trong `split=test` có 10 VQA bị drop; 9 dòng nằm trong prediction outputs đã dùng để tính benchmark, còn `vqa_id=9546` không có trong prediction files vì `is_checked=false`.
- Tất cả prediction files của GPT-5.2/GPT-5.5 đã được prune từ 1,410 xuống 1,401 dòng và tính lại metrics.

## Độ Đầy Đủ Của Kết Quả

| Model | Nhóm output | Conditions | Rows sau prune |
| --- | --- | ---: | ---: |
| `gpt_5_2` | `gpt52_full_20260430` | 8/8 | 11,208 |
| `gpt_5_5` | `gpt55_kg_20260430_074852` + `gpt55_no_kg_20260430_074852` | 8/8 | 11,208 |
| tất cả | combined | **16/16** | **22,416** |

Độ đầy đủ của classifier cache:

| Model | Số dòng classifier | Ghi chú |
| --- | ---: | --- |
| `gpt_5_2` | 1,410 | Cache gốc chưa prune; metrics classifier được tính trên prediction rows còn lại. |
| `gpt_5_5` | 1,410 | Cache gốc chưa prune; metrics classifier được tính trên prediction rows còn lại. |

## Accuracy Tổng Thể

| Model | Condition | Đúng / Tổng | Accuracy | Parse failure | QType classifier | Avg answer latency |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `gpt_5_2` | `no_kg_0shot` | 1,236 / 1,401 | 88.22% | 0.50% | - | 5.37s |
| `gpt_5_2` | `no_kg_1shot` | 1,242 / 1,401 | 88.65% | 0.36% | - | 6.16s |
| `gpt_5_2` | `no_kg_2shot` | 1,209 / 1,401 | 86.30% | 1.36% | - | 15.16s |
| `gpt_5_2` | `hybrid` | 1,243 / 1,401 | 88.72% | 1.07% | 96.36% | 5.14s |
| `gpt_5_2` | `graph_only` | 1,237 / 1,401 | 88.29% | 1.21% | 96.36% | 5.86s |
| `gpt_5_2` | `vector_only` | 1,221 / 1,401 | 87.15% | 1.43% | 96.36% | 12.91s |
| `gpt_5_2` | `bm25` | 1,221 / 1,401 | 87.15% | 1.43% | 96.36% | 7.38s |
| `gpt_5_2` | `oracle` | 1,335 / 1,401 | 95.29% | 0.64% | - | 4.90s |
| `gpt_5_5` | `no_kg_0shot` | 1,270 / 1,401 | 90.65% | **0.00%** | - | 7.58s |
| `gpt_5_5` | `no_kg_1shot` | 1,273 / 1,401 | 90.86% | **0.00%** | - | 8.33s |
| `gpt_5_5` | `no_kg_2shot` | 1,274 / 1,401 | 90.94% | **0.00%** | - | 13.50s |
| `gpt_5_5` | `hybrid` | 1,271 / 1,401 | 90.72% | **0.00%** | **97.50%** | 7.22s |
| `gpt_5_5` | `graph_only` | 1,269 / 1,401 | 90.58% | **0.00%** | **97.50%** | 7.38s |
| `gpt_5_5` | `vector_only` | 1,257 / 1,401 | 89.72% | **0.00%** | **97.50%** | 7.26s |
| `gpt_5_5` | `bm25` | 1,259 / 1,401 | 89.86% | 0.71% | **97.50%** | 6.09s |
| `gpt_5_5` | `oracle` | **1,338 / 1,401** | **95.50%** | 0.93% | - | **4.54s** |

## Nhận Xét Chính

- `gpt_5_5` vẫn mạnh hơn `gpt_5_2` nhất quán trên toàn bộ các condition có thể so sánh.
- Non-oracle tốt nhất của `gpt_5_2` là `hybrid` với 88.72%.
- Non-oracle tốt nhất của `gpt_5_5` là `no_kg_2shot` với 90.94%; `hybrid` đạt 90.72%, kém 3 câu đúng trên 1,401 mẫu.
- `oracle` vẫn là upper bound rõ ràng: `gpt_5_2` đạt 95.29%, `gpt_5_5` đạt 95.50%.
- GPT-5.5 ổn định hơn về parsing: không có parse failure ở `no_kg_*`, `hybrid`, `graph_only`, và `vector_only`.

## So Sánh Model Theo Condition

| Condition | GPT-5.2 | GPT-5.5 | Delta của GPT-5.5 |
| --- | ---: | ---: | ---: |
| `no_kg_0shot` | 88.22% | **90.65%** | +2.43 pp |
| `no_kg_1shot` | 88.65% | **90.86%** | +2.21 pp |
| `no_kg_2shot` | 86.30% | **90.94%** | **+4.64 pp** |
| `hybrid` | 88.72% | **90.72%** | +2.00 pp |
| `graph_only` | 88.29% | **90.58%** | +2.28 pp |
| `vector_only` | 87.15% | **89.72%** | +2.57 pp |
| `bm25` | 87.15% | **89.86%** | +2.71 pp |
| `oracle` | 95.29% | **95.50%** | +0.21 pp |

## Retrieval Metrics

| Model | Condition | Precision@10 | Recall@10 | F1@10 |
| --- | --- | ---: | ---: | ---: |
| `gpt_5_2` | `hybrid` | 0.3322 | 0.4079 | 0.3559 |
| `gpt_5_2` | `graph_only` | 0.3321 | 0.4076 | 0.3558 |
| `gpt_5_2` | `vector_only` | 0.0289 | 0.2358 | 0.0509 |
| `gpt_5_2` | `bm25` | 0.0147 | 0.1332 | 0.0263 |
| `gpt_5_2` | `oracle` | **1.0000** | **1.0000** | **1.0000** |
| `gpt_5_5` | `hybrid` | 0.3613 | 0.4914 | 0.3990 |
| `gpt_5_5` | `graph_only` | 0.3607 | 0.4882 | 0.3980 |
| `gpt_5_5` | `vector_only` | 0.0298 | 0.2454 | 0.0525 |
| `gpt_5_5` | `bm25` | 0.0161 | 0.1486 | 0.0288 |
| `gpt_5_5` | `oracle` | **1.0000** | **1.0000** | **1.0000** |

Nếu bỏ qua `oracle`, retrieval tốt nhất là `gpt_5_5 hybrid` với F1@10 = **0.3990**.

## Kết Luận Báo Cáo

1. Dùng `oracle` như upper-bound evidence result, không xem là setting triển khai.
2. Dùng `hybrid` làm KG retrieval condition chính vì đây là non-oracle tốt nhất của `gpt_5_2` và vẫn cạnh tranh với `gpt_5_5`.
3. Ghi rõ benchmark đã được revised từ 1,410 xuống 1,401 câu sau khi loại 9 prediction rows bị ảnh hưởng.
