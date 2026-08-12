"""FastAPI application for the local canonical card catalog."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from .config import DATABASE_PATH
from .database import CatalogDatabase


def create_app(database_path: Path | str = DATABASE_PATH) -> FastAPI:
    database = CatalogDatabase(database_path)
    database.initialize()
    app = FastAPI(
        title="Local Pokemon TCG Card API",
        version="0.1.0",
        description="Canonical local card data with source provenance. User inventory is separate.",
    )

    @app.get("/health")
    def health() -> dict:
        with database.connect() as connection:
            counts = connection.execute(
                "SELECT (SELECT COUNT(*) FROM sets) AS sets, (SELECT COUNT(*) FROM cards) AS cards"
            ).fetchone()
        return {"status": "ok", "sets": counts["sets"], "cards": counts["cards"]}

    @app.get("/cards")
    def cards(
        set_code: str | None = None,
        number: str | None = None,
        name: str | None = None,
        language: str = "en-US",
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> dict:
        filters = ["c.language = ?"]
        parameters: list[object] = [language]
        if set_code:
            filters.append(
                "EXISTS (SELECT 1 FROM set_codes sc WHERE sc.set_id = s.id AND sc.code = ? COLLATE NOCASE)"
            )
            parameters.append(set_code.strip())
        if number:
            filters.append("ltrim(c.number, '0') = ltrim(?, '0')")
            parameters.append(number.strip())
        if name:
            filters.append("c.name LIKE ? COLLATE NOCASE")
            parameters.append(f"%{name.strip()}%")
        return _card_page(database, filters, parameters, limit, offset)

    @app.get("/cards/search")
    def search_cards(
        q: str = Query(..., min_length=1),
        set_code: str | None = None,
        language: str = "en-US",
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> dict:
        query = q.strip()
        filters = ["c.language = ?", "(c.name LIKE ? COLLATE NOCASE OR c.number = ?)"]
        parameters: list[object] = [language, f"%{query}%", query]
        if set_code:
            filters.append(
                "EXISTS (SELECT 1 FROM set_codes sc WHERE sc.set_id = s.id AND sc.code = ? COLLATE NOCASE)"
            )
            parameters.append(set_code.strip())
        return _card_page(database, filters, parameters, limit, offset)

    @app.get("/cards/{card_id}")
    def card(card_id: str) -> dict:
        with database.connect() as connection:
            row = connection.execute(_CARD_SELECT + " WHERE c.id = ?", (card_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Card not found")
            result = dict(row)
            text_rows = connection.execute(
                """
                SELECT position, kind, name, text, cost_json,
                       damage_amount, damage_suffix
                FROM card_text_entries WHERE card_id = ? ORDER BY position
                """,
                (card_id,),
            ).fetchall()
            result["text_entries"] = [
                {
                    **dict(item),
                    "cost": json.loads(item["cost_json"]) if item["cost_json"] else None,
                }
                for item in text_rows
            ]
            for item in result["text_entries"]:
                item.pop("cost_json", None)
            result["images"] = [
                dict(item)
                for item in connection.execute(
                    """
                    SELECT image_format, face, variant, url
                    FROM card_images WHERE card_id = ?
                    ORDER BY image_format, face, variant
                    """,
                    (card_id,),
                ).fetchall()
            ]
            result["provenance"] = [
                dict(item)
                for item in connection.execute(
                    """
                    SELECT s.source_key, s.name AS source_name, cs.source_card_id,
                           sf.source_url, sf.sha256, sf.upstream_hash,
                           sf.downloaded_at, sf.imported_at, cs.raw_record_index,
                           cs.record_sha256
                    FROM card_sources cs
                    JOIN sources s ON s.id = cs.source_id
                    JOIN source_files sf ON sf.id = cs.source_file_id
                    WHERE cs.card_id = ?
                    """,
                    (card_id,),
                ).fetchall()
            ]
            result["variants"] = [
                {
                    **dict(item),
                    "images": [
                        dict(image)
                        for image in connection.execute(
                            """
                            SELECT image_format, face, layer, url
                            FROM card_variant_images
                            WHERE variant_id = ?
                            ORDER BY image_format, face, layer
                            """,
                            (item["id"],),
                        ).fetchall()
                    ],
                }
                for item in connection.execute(
                    """
                    SELECT id, source_card_id, long_form_id, finish_type,
                           finish_mask, primary_image_url
                    FROM card_variants WHERE card_id = ? ORDER BY id
                    """,
                    (card_id,),
                ).fetchall()
            ]
        return result

    @app.get("/sets")
    def sets(
        language: str = "en-US",
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> dict:
        with database.connect() as connection:
            total = connection.execute(
                "SELECT COUNT(*) AS count FROM sets WHERE language = ?", (language,)
            ).fetchone()["count"]
            rows = connection.execute(
                """
                SELECT s.id, s.name, s.code, s.language, s.card_count,
                       s.release_date, COUNT(c.id) AS imported_card_count
                FROM sets s LEFT JOIN cards c ON c.set_id = s.id
                WHERE s.language = ?
                GROUP BY s.id
                ORDER BY s.name COLLATE NOCASE
                LIMIT ? OFFSET ?
                """,
                (language, limit, offset),
            ).fetchall()
            items = []
            for row in rows:
                item = dict(row)
                item["codes"] = [
                    dict(code)
                    for code in connection.execute(
                        "SELECT code, code_type FROM set_codes WHERE set_id = ? ORDER BY code_type, code",
                        (row["id"],),
                    ).fetchall()
                ]
                items.append(item)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.get("/sets/{set_id}/cards")
    def set_cards(
        set_id: str,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> dict:
        with database.connect() as connection:
            exists = connection.execute("SELECT 1 FROM sets WHERE id = ?", (set_id,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Set not found")
        return _card_page(database, ["c.set_id = ?"], [set_id], limit, offset)

    return app


_CARD_SELECT = """
SELECT c.id, c.name, c.card_type, c.number, c.number_numeric,
       c.printed_total, c.hp, c.regulation_mark, c.rarity, c.stage,
       c.language, c.primary_image_url, c.validation_status,
       s.id AS set_id, s.name AS set_name, s.code AS set_code
FROM cards c JOIN sets s ON s.id = c.set_id
"""


def _card_page(
    database: CatalogDatabase,
    filters: list[str],
    parameters: list[object],
    limit: int,
    offset: int,
) -> dict:
    where = " WHERE " + " AND ".join(filters) if filters else ""
    with database.connect() as connection:
        total = connection.execute(
            "SELECT COUNT(*) AS count FROM cards c JOIN sets s ON s.id = c.set_id" + where,
            parameters,
        ).fetchone()["count"]
        rows = connection.execute(
            _CARD_SELECT
            + where
            + " ORDER BY s.name COLLATE NOCASE, c.number_numeric, c.number LIMIT ? OFFSET ?",
            [*parameters, limit, offset],
        ).fetchall()
    return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}
