from __future__ import annotations

import base64
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vifood_verify.model import _image_to_data_url


class ModelImageTests(unittest.TestCase):
    def test_large_image_is_compressed_before_encoding(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "large.png"
            Image.new("RGB", (2400, 1800), (120, 80, 40)).save(path, format="PNG")

            data_url = _image_to_data_url(
                path,
                max_side=800,
                max_bytes=100_000,
                jpeg_quality=80,
            )

        header, encoded = data_url.split(",", 1)
        payload = base64.b64decode(encoded)
        self.assertEqual(header, "data:image/jpeg;base64")
        self.assertLessEqual(len(payload), 100_000)


if __name__ == "__main__":
    unittest.main()
