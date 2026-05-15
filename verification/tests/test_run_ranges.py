from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vifood_verify.data import VQARow
from vifood_verify.run import _select_global_row_range


def row(vqa_id: int) -> VQARow:
    return VQARow(
        row={"vqa_id": vqa_id, "image_id": f"image{vqa_id}"},
        split="train",
        data_dir=Path("."),
    )


class RunRangeTests(unittest.TestCase):
    def test_global_row_range_spans_splits_in_order(self) -> None:
        rows_by_split = {
            "train": [row(1), row(2), row(3)],
            "validation": [row(4), row(5)],
        }

        selected = _select_global_row_range(rows_by_split, row_start=3, row_end=5)

        self.assertEqual([item.vqa_id for item in selected["train"]], [3])
        self.assertEqual([item.vqa_id for item in selected["validation"]], [4, 5])
        self.assertEqual(selected["train"][0].row["_global_row_index"], 3)
        self.assertEqual(selected["validation"][0].row["_global_row_index"], 4)


if __name__ == "__main__":
    unittest.main()
