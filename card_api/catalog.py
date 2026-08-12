"""Source-independent, exact local catalog queries shared by API consumers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import DATABASE_PATH
from .database import CatalogDatabase


@dataclass(frozen=True)
class CatalogCard:
    id: str
    set_id: str
    set_code: str
    set_name: str
    card_name: str
    card_number: str
    printed_total: str
    regulation_mark: str
    hp: int | None
    rarity: str
    image_url: str


@dataclass(frozen=True)
class ExactCardResult:
    status: str
    card: CatalogCard | None = None
    match_count: int = 0


def find_exact_card(
    set_code: str,
    card_number: str,
    *,
    database_path: Path | str = DATABASE_PATH,
) -> ExactCardResult:
    """Match only one exact printed set code and normalized card number."""
    code = set_code.strip().upper()
    number = card_number.strip()
    if not code or not number or not number.isdigit():
        return ExactCardResult("invalid_input")

    database = CatalogDatabase(database_path)
    if not database.path.is_file():
        return ExactCardResult("catalog_unavailable")
    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT c.id, c.set_id, s.code AS set_code, s.name AS set_name,
                   c.name AS card_name, c.number AS card_number,
                   COALESCE(c.printed_total, '') AS printed_total,
                   COALESCE(c.regulation_mark, '') AS regulation_mark,
                   c.hp, COALESCE(c.rarity, '') AS rarity,
                   COALESCE(c.primary_image_url, '') AS image_url
            FROM cards c
            JOIN sets s ON s.id = c.set_id
            WHERE c.language = 'en-US'
              AND ltrim(c.number, '0') = ltrim(?, '0')
              AND EXISTS (
                  SELECT 1 FROM set_codes sc
                  WHERE sc.set_id = s.id AND sc.code = ? COLLATE NOCASE
              )
            ORDER BY c.id
            """,
            (number, code),
        ).fetchall()

    if not rows:
        return ExactCardResult("no_match")
    if len(rows) != 1:
        return ExactCardResult("ambiguous", match_count=len(rows))
    row = rows[0]
    return ExactCardResult(
        "exact",
        CatalogCard(
            id=row["id"],
            set_id=row["set_id"],
            set_code=code,
            set_name=row["set_name"],
            card_name=row["card_name"],
            card_number=row["card_number"],
            printed_total=row["printed_total"],
            regulation_mark=row["regulation_mark"],
            hp=row["hp"],
            rarity=row["rarity"],
            image_url=row["image_url"],
        ),
        match_count=1,
    )
