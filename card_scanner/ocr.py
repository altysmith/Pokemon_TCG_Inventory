"""Tesseract OCR with evidence preservation across image treatments."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from .catalog import known_set_codes
from .parser import (
    CodeCandidate,
    NumberCandidate,
    ParsedCard,
    extract_code_observations,
    extract_number_observations,
    parse_card_text,
)


@dataclass(frozen=True)
class TextObservation:
    text: str
    source: str
    low_quality: bool = False


@dataclass(frozen=True)
class OcrResult:
    raw_text: str
    parsed: ParsedCard
    processed_image: Image.Image
    code_candidates: tuple[CodeCandidate, ...] = ()
    number_candidates: tuple[NumberCandidate, ...] = ()
    observations: tuple[TextObservation, ...] = ()
    ocr_engine: str = ""
    evidence_text: str = ""
    literal_readings: tuple["LiteralReading", ...] = ()
    primary_confidence: float = 0.0


@dataclass(frozen=True)
class LiteralReading:
    text: str
    confidence: float
    variant: str = ""


_RAPID_OCR_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def _rapidocr_engine():
    from rapidocr import RapidOCR

    return RapidOCR()


def warm_up_ocr() -> None:
    """Load RapidOCR models before the browser offers its first capture."""
    with _RAPID_OCR_LOCK:
        _rapidocr_engine()


def _run_rapidocr(image: Image.Image) -> tuple[LiteralReading, ...]:
    """Read scene text without a card-code whitelist or catalog hints."""
    import numpy as np

    with _RAPID_OCR_LOCK:
        output = _rapidocr_engine()(np.asarray(image.convert("RGB")))
    texts = tuple(getattr(output, "txts", None) or ())
    scores = tuple(getattr(output, "scores", None) or ())
    readings = []
    for index, text in enumerate(texts):
        value = " ".join(str(text).split())
        if value:
            confidence = float(scores[index]) if index < len(scores) else 0.0
            readings.append(LiteralReading(value, confidence))
    return tuple(readings)


def _rapidocr_variants(image: Image.Image) -> tuple[tuple[str, Image.Image], ...]:
    target_width = min(2400, max(1000, image.width * 4))
    scale = target_width / max(1, image.width)
    large = image.resize(
        (target_width, max(80, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    gray = ImageOps.autocontrast(ImageOps.grayscale(large), cutoff=1).convert("RGB")
    return (
        ("original", image.convert("RGB")),
        ("enlarged_color", large),
        ("enlarged_gray", gray),
    )


def find_tesseract() -> str:
    candidates = [
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise FileNotFoundError(
        "Tesseract OCR was not found. Install it from "
        "https://github.com/UB-Mannheim/tesseract/wiki"
    )


def _variants(image: Image.Image) -> list[Image.Image]:
    # Keep moderate and large scales because interpolation helps different badge
    # styles differently. Color channels separate foil glare from printed ink.
    legacy_gray = ImageOps.grayscale(image)
    legacy_width = max(1200, legacy_gray.width * 6)
    legacy_scale = legacy_width / max(1, legacy_gray.width)
    legacy_resized = legacy_gray.resize(
        (legacy_width, max(80, round(legacy_gray.height * legacy_scale))),
        Image.Resampling.LANCZOS,
    )
    legacy = ImageOps.autocontrast(
        ImageEnhance.Contrast(legacy_resized)
        .enhance(2.3)
        .filter(ImageFilter.UnsharpMask(radius=2, percent=180, threshold=2)),
        cutoff=1,
    )

    target_width = max(2200, image.width * 10)
    scale = target_width / max(1, image.width)
    resized = image.resize(
        (target_width, max(120, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    gray = ImageOps.grayscale(resized)
    _red, green, blue = resized.split()

    def prepared(channel: Image.Image) -> Image.Image:
        return ImageOps.autocontrast(
            ImageEnhance.Contrast(channel)
            .enhance(2.0)
            .filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=2)),
            cutoff=1,
        )

    def threshold(channel: Image.Image, level: int, border: int = 255) -> Image.Image:
        binary = prepared(channel).point(lambda value: 255 if value > level else 0)
        return ImageOps.expand(binary, border=80, fill=border)

    return [
        legacy,
        legacy.point(lambda value: 255 if value > 145 else 0),
        legacy.point(lambda value: 255 if value > 175 else 0),
        ImageOps.expand(prepared(gray), border=80, fill=255),
        threshold(gray, 145),
        threshold(gray, 175),
        threshold(gray, 220, border=0),
        threshold(gray, 235),
        threshold(green, 220, border=0),
        threshold(green, 235, border=0),
        threshold(blue, 160),
    ]


def _source_for_variant(index: int) -> tuple[str, bool]:
    if index <= 2:
        return "legacy_gray", False
    if index <= 7:
        return "large_gray", False
    if index <= 9:
        return "green_channel", False
    return "blue_channel", True


def _run_tesseract(image: Image.Image, executable: str, psm: int = 7) -> str:
    with tempfile.TemporaryDirectory(prefix="card_scan_") as temp_dir:
        image_path = Path(temp_dir) / "crop.png"
        image.save(image_path)
        command = [
            executable,
            str(image_path),
            "stdout",
            "--psm",
            str(psm),
            "-l",
            "eng",
            "-c",
            "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/\\-|",
        ]
        completed = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=30
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "Tesseract OCR failed")
        return completed.stdout.strip()


def build_evidence(
    observations: Iterable[TextObservation], known_codes: Iterable[str] | None = None
) -> tuple[tuple[CodeCandidate, ...], tuple[NumberCandidate, ...]]:
    """Aggregate observations without counting correlated treatments repeatedly."""
    texts = tuple(observations)
    codes = frozenset(known_codes if known_codes is not None else known_set_codes())

    code_buckets: dict[str, list[tuple[object, TextObservation]]] = {}
    number_buckets: dict[str, list[tuple[object, TextObservation]]] = {}
    for text_observation in texts:
        for item in extract_code_observations(text_observation.text, codes):
            code_buckets.setdefault(item.value, []).append((item, text_observation))
        for item in extract_number_observations(text_observation.text):
            number_buckets.setdefault(item.value, []).append((item, text_observation))

    code_candidates: list[CodeCandidate] = []
    for value, items in code_buckets.items():
        per_source: dict[str, int] = {}
        reasons: set[str] = set()
        low_only = True
        for item, observation in items:
            per_source[observation.source] = max(
                per_source.get(observation.source, 0), item.weight
            )
            reasons.add(item.kind)
            low_only = low_only and observation.low_quality
        score = max(per_source.values())
        if len(per_source) >= 2:
            score += 2
            reasons.add("independent_repetition")
        if low_only:
            score -= 3
            reasons.add("single_low_quality_source")
        code_candidates.append(
            CodeCandidate(
                value,
                score,
                tuple(sorted(per_source)),
                tuple(sorted(reasons)),
            )
        )

    number_candidates: list[NumberCandidate] = []
    for value, items in number_buckets.items():
        per_source: dict[str, int] = {}
        totals: set[str] = set()
        reasons: set[str] = set()
        right_side = False
        low_only = True
        for item, observation in items:
            per_source[observation.source] = max(
                per_source.get(observation.source, 0), item.weight
            )
            if item.total:
                totals.add(item.total)
            right_side = right_side or item.side == "right"
            reasons.add(item.kind)
            low_only = low_only and observation.low_quality
        score = max(per_source.values())
        if len(per_source) >= 2:
            score += 2
            reasons.add("independent_repetition")
        if low_only:
            score -= 3
            reasons.add("single_low_quality_source")
        number_candidates.append(
            NumberCandidate(
                value,
                score,
                tuple(sorted(per_source)),
                tuple(sorted(totals)),
                right_side,
                tuple(sorted(reasons)),
            )
        )

    code_candidates.sort(key=lambda item: (-item.score, item.value))
    number_candidates.sort(key=lambda item: (-item.score, len(item.value), item.value))
    return tuple(code_candidates), tuple(number_candidates)


def scan_crop(image: Image.Image, derive_card_candidates: bool = True) -> OcrResult:
    """Read literal text first, then derive optional card interpretations."""
    observations: list[TextObservation] = []
    literal_readings: list[LiteralReading] = []

    # This is the primary generic reader. It has no expected code, number, or
    # character whitelist. All variants remain one correlated evidence source.
    try:
        for variant_name, variant in _rapidocr_variants(image):
            readings = _run_rapidocr(variant)
            if not readings:
                continue
            combined = LiteralReading(
                " ".join(item.text for item in readings),
                sum(item.confidence for item in readings) / len(readings),
                variant_name,
            )
            literal_readings.append(combined)
            observation = TextObservation(
                combined.text,
                "rapidocr",
                low_quality=combined.confidence < 0.65,
            )
            observations.append(observation)
    except (ImportError, OSError, RuntimeError, ValueError):
        pass

    # Tesseract is now a true fallback. It runs only if RapidOCR found no text.
    variants: list[Image.Image] = []
    if not literal_readings:
        variants = _variants(image)
        try:
            executable = find_tesseract()
        except FileNotFoundError:
            executable = ""
        if executable:
            for index, variant in enumerate(variants):
                source, low_quality = _source_for_variant(index)
                for psm in (7, 6):
                    text = _run_tesseract(variant, executable, psm)
                    if text:
                        observations.append(TextObservation(text, source, low_quality))

    evidence_text = " | ".join(dict.fromkeys(item.text for item in observations))
    best_literal = max(
        literal_readings,
        key=lambda item: (item.confidence, len(item.text)),
        default=None,
    )
    raw_text = best_literal.text if best_literal else evidence_text
    all_code_candidates, all_number_candidates = (
        build_evidence(observations) if derive_card_candidates else ((), ())
    )
    best_observation = (
        TextObservation(
            best_literal.text,
            "rapidocr_primary",
            low_quality=best_literal.confidence < 0.65,
        ),
    ) if best_literal else ()
    primary_codes, primary_numbers = (
        build_evidence(best_observation) if derive_card_candidates else ((), ())
    )
    # A successful primary reading cannot be outvoted by image treatments from
    # either engine. Secondary evidence fills only what the best literal read
    # missed; it never rewrites that literal result.
    code_candidates = primary_codes or all_code_candidates
    number_candidates = primary_numbers or all_number_candidates
    parsed = parse_card_text(raw_text) if derive_card_candidates else ParsedCard()
    if not parsed.set_code and code_candidates:
        parsed = ParsedCard(
            code_candidates[0].value,
            parsed.card_number,
            parsed.set_total,
        )
    if not parsed.card_number and number_candidates:
        candidate = number_candidates[0]
        parsed = ParsedCard(
            parsed.set_code,
            candidate.value,
            candidate.totals[0] if candidate.totals else "",
        )
    return OcrResult(
        raw_text,
        parsed,
        variants[0] if variants else image,
        code_candidates[:8],
        number_candidates[:10],
        tuple(observations),
        "RapidOCR" if best_literal else "Tesseract fallback",
        evidence_text,
        tuple(literal_readings),
        best_literal.confidence if best_literal else 0.0,
    )
