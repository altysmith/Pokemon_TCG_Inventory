"""Measure layout-aware footer OCR against corrected webcam benchmark rows."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from PIL import Image

from card_scanner.ocr import scan_crop
from app import extract_footer_fields


ROOT = Path(__file__).resolve().parent


def _letters(value: str) -> tuple[str, str]:
    parts = value.upper().split()
    if len(parts) >= 2:
        return parts[0], parts[1]
    if len(parts) == 1 and len(parts[0]) == 1:
        return parts[0], ""
    return "", parts[0] if parts else ""


def _numbers(value: str) -> tuple[str, str]:
    parts = re.findall(r"\d+", value)
    return (parts[0] if parts else "", parts[1] if len(parts) > 1 else "")


def main() -> None:
    with (ROOT / "ocr_reads_it5.csv").open(newline="", encoding="utf-8-sig") as source:
        rows = [row for row in csv.DictReader(source) if row["image_name"].startswith("webcam_")]

    correct = dict.fromkeys(("regulation_mark", "set_code", "card_number", "set_total"), 0)
    eligible = correct.copy()
    complete = 0
    for index, row in enumerate(rows, 1):
        expected_reg, expected_set = _letters(row["corrected_letters"])
        expected_number, expected_total = _numbers(row["corrected_numbers"])
        expected = (expected_reg, expected_set, expected_number, expected_total)
        with Image.open(row["crop_path"]) as opened:
            result = scan_crop(opened.convert("RGB"), derive_card_candidates=False)
            actual = extract_footer_fields(result.raw_text)
        for field, wanted, got in zip(correct, expected, actual):
            if wanted:
                eligible[field] += 1
                correct[field] += got == wanted
        complete += actual == expected
        print(f"{index:02d} expected={'|'.join(expected):16} found={'|'.join(actual):16}")

    print(f"rows={len(rows)} complete={complete}")
    for field in correct:
        print(f"{field}={correct[field]}/{eligible[field]}")


if __name__ == "__main__":
    main()
