from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "src" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from export_hf_dataset import normalize_row, normalize_triples_used


def temp_dir() -> TemporaryDirectory[str]:
    root = Path(os.environ.get("VIFOODVQA_TEST_TMP", "C:/tmp"))
    root.mkdir(parents=True, exist_ok=True)
    return TemporaryDirectory(dir=root)


class ExportHFDatasetTest(unittest.TestCase):
    def test_normalize_triples_used_removes_non_schema_fields(self) -> None:
        triples = normalize_triples_used(
            [
                {
                    "target": "T",
                    "subject": "S",
                    "evidence": None,
                    "relation": "R",
                    "source_url": None,
                }
            ]
        )

        self.assertEqual(triples, [{"subject": "S", "relation": "R", "target": "T"}])

    def test_normalize_row_reuses_existing_image_without_downloading(self) -> None:
        with temp_dir() as tmp:
            hf_dir = Path(tmp)
            image_dir = hf_dir / "images"
            image_dir.mkdir()
            (image_dir / "image001.png").write_bytes(b"fake")

            row = {
                "vqa_id": 1,
                "image_id": "image001",
                "split": "train",
                "is_checked": False,
                "is_drop": False,
                "qtype": "ingredients",
                "question": "Q?",
                "choice_a": "A",
                "choice_b": "B",
                "choice_c": "C",
                "choice_d": "D",
                "answer": "A",
                "rationale": "R",
                "triples_used": [
                    {
                        "subject": "s",
                        "relation": "r",
                        "target": "t",
                        "evidence": None,
                        "source_url": None,
                    }
                ],
                "verify_decision": None,
                "image": {"image_url": "https://example.com/image001.png", "is_drop": False},
            }

            output = normalize_row(
                row,
                hf_dir=hf_dir,
                image_dir=image_dir,
                download_images=False,
                download_source="all",
                overwrite_images=False,
            )

            self.assertIsNotNone(output)
            self.assertEqual(output["image"], "images/image001.png")
            self.assertEqual(output["triples_used"], [{"subject": "s", "relation": "r", "target": "t"}])

    def test_normalize_row_skips_when_local_image_is_missing_and_download_disabled(self) -> None:
        with temp_dir() as tmp:
            hf_dir = Path(tmp)
            image_dir = hf_dir / "images"
            image_dir.mkdir()

            row = {
                "vqa_id": 1,
                "image_id": "image001",
                "split": "train",
                "is_checked": False,
                "is_drop": False,
                "qtype": "ingredients",
                "question": "Q?",
                "choice_a": "A",
                "choice_b": "B",
                "choice_c": "C",
                "choice_d": "D",
                "answer": "A",
                "rationale": "R",
                "triples_used": [{"subject": "s", "relation": "r", "target": "t"}],
                "verify_decision": None,
                "image": {"image_url": "https://example.com/image001.png", "is_drop": False},
            }

            output = normalize_row(
                row,
                hf_dir=hf_dir,
                image_dir=image_dir,
                download_images=False,
                download_source="all",
                overwrite_images=False,
            )

            self.assertIsNone(output)


if __name__ == "__main__":
    unittest.main()
