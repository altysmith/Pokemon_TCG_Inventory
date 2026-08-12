"""Validation that records data defects without silently repairing source data."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    field: str
    message: str


def validate_set(entry: dict, source_set_id: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not source_set_id.strip():
        issues.append(ValidationIssue("error", "set.id", "Set identifier is missing."))
    for field in ("name", "abbr", "path", "hash"):
        if not isinstance(entry.get(field), str) or not entry[field].strip():
            severity = "warning" if field == "name" else "error"
            issues.append(ValidationIssue(severity, f"set.{field}", f"Set {field} is missing."))
    count = entry.get("num")
    if not isinstance(count, int) or count < 0:
        issues.append(ValidationIssue("error", "set.num", "Set card count is invalid."))
    return issues


def validate_card(card: object) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not isinstance(card, dict):
        return [ValidationIssue("error", "card", "Card record is not an object.")]

    if not isinstance(card.get("name"), str) or not card["name"].strip():
        issues.append(ValidationIssue("error", "name", "Card name is missing."))
    if not isinstance(card.get("card_type"), str) or not card["card_type"].strip():
        issues.append(ValidationIssue("error", "card_type", "Card type is missing."))

    collector = card.get("collector_number")
    if not isinstance(collector, dict):
        issues.append(ValidationIssue("error", "collector_number", "Collector number is missing."))
    else:
        numerator = collector.get("numerator")
        denominator = collector.get("denominator")
        if not isinstance(numerator, str) or not numerator.strip():
            issues.append(ValidationIssue("error", "collector_number.numerator", "Card number is missing."))
        if denominator is not None and (
            not isinstance(denominator, str) or not denominator.strip()
        ):
            issues.append(ValidationIssue("warning", "collector_number.denominator", "Printed set total is invalid."))
        numeric = collector.get("numeric")
        if numeric is not None and (not isinstance(numeric, int) or numeric < 0):
            issues.append(ValidationIssue("warning", "collector_number.numeric", "Numeric card number is invalid."))

    hp = card.get("hp")
    if hp is not None and (not isinstance(hp, int) or hp <= 0):
        issues.append(ValidationIssue("error", "hp", "HP must be a positive integer when present."))
    if card.get("card_type") == "POKEMON" and hp is None:
        issues.append(ValidationIssue("warning", "hp", "Pokemon card has no HP value."))

    mark = card.get("regulation_mark")
    if mark is not None and (
        not isinstance(mark, str) or len(mark.strip()) != 1 or not mark.strip().isalpha()
    ):
        issues.append(ValidationIssue("warning", "regulation_mark", "Regulation mark is not one letter."))

    text_entries = card.get("text", [])
    if text_entries is not None and not isinstance(text_entries, list):
        issues.append(ValidationIssue("error", "text", "Card text entries are not a list."))
    elif isinstance(text_entries, list):
        for position, item in enumerate(text_entries):
            prefix = f"text[{position}]"
            if not isinstance(item, dict):
                issues.append(ValidationIssue("error", prefix, "Text entry is not an object."))
                continue
            if not isinstance(item.get("kind"), str) or not item["kind"].strip():
                issues.append(ValidationIssue("error", f"{prefix}.kind", "Text entry kind is missing."))
            if item.get("kind") == "ATTACK":
                if not isinstance(item.get("name"), str) or not item["name"].strip():
                    issues.append(ValidationIssue("error", f"{prefix}.name", "Attack name is missing."))
                if "cost" in item and not isinstance(item["cost"], list):
                    issues.append(ValidationIssue("error", f"{prefix}.cost", "Attack cost is not a list."))

    front_urls = list(_front_image_urls(card.get("images")))
    if not front_urls:
        issues.append(ValidationIssue("warning", "images", "No front image URL is present."))
    for field, url in front_urls:
        parsed = urlparse(url) if isinstance(url, str) else None
        if parsed is None or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            issues.append(ValidationIssue("error", field, "Image URL is invalid."))
    return issues


def _front_image_urls(images: object):
    if not isinstance(images, dict):
        return
    for source_name, formats in images.items():
        if not isinstance(formats, dict):
            continue
        for image_format, variants in formats.items():
            if isinstance(variants, dict) and "front" in variants:
                yield f"images.{source_name}.{image_format}.front", variants["front"]
