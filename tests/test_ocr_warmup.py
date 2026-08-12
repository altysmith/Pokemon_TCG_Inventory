import unittest
from unittest.mock import patch

from card_scanner.ocr import warm_up_ocr


class OcrWarmupTests(unittest.TestCase):
    def test_warmup_initializes_cached_engine(self):
        with patch("card_scanner.ocr._rapidocr_engine") as engine:
            warm_up_ocr()

        engine.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
