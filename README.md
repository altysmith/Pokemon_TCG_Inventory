# Pokémon Card Collection

**Current build: Iteration 18 — Search-first collection intake**

This local browser app provides catalog search, quantity-based collection management, and read-only deck-list checking. The former webcam OCR experiment is retained as dormant legacy code but is no longer part of the normal interface.

## Run it

Double-click the **Pokemon Card Collection** desktop icon. It starts the private local server without a terminal window and opens the collection in its own Edge or Chrome app window. Use the navigation to switch between **Search**, **Collection**, and **Deck Check**. Closing that app window automatically stops the local server.

The project-folder fallback is **`Start Pokemon Collection.bat`**. It launches the same app-style window and has the same automatic shutdown behavior. The desktop shortcut points to the project files, so keep the project in its current Desktop location.

The launcher uses an operating-system-level single-instance lock plus a server API version check. Double-clicking it again reports that the collection is already open instead of starting another server. If a manually started or older server already owns the port, startup stops with a clear instruction to close it; it never shares the port with incompatible code.

### Project folder map

- `web/` — the active Search, Collection, and Deck Check interface.
- `app.py`, `inventory.py`, `deck_checker.py`, `saved_decks.py` — active application code.
- `card_api/` and `data/` — rebuildable canonical card catalog and preserved Malie source data.
- `user_data/` — personal inventory, saved decks, backups, and ignored runtime lock files.
- `tests/` — portable automated tests and their small tracked fixtures.
- `tools/` — optional catalog update/API launchers and their dependency helper.
- `legacy_webcam_scanner/` — dormant webcam UI plus ignored historical OCR evidence.
- `collection_showcase/` — separate read-only collection snapshot viewer.

Only **`Start Pokemon Collection.bat`** launches the normal collection application. Optional catalog maintenance launchers are tucked under `tools/` and do not launch the collection UI.

RapidOCR, ONNX Runtime, Tesseract, and the required Python runtime are installed on this machine. `requirements.txt` is included for installing the project on another computer.

## Local card database and API

This repository contains the local collection application and the `card_api` catalog service. The dormant webcam experiment is isolated under `legacy_webcam_scanner/` and is not linked from the application.

The catalog uses [Malie.io's formatted TCGL exports](https://malie.io/static/index.html) as its primary source. Its pipeline is:

```text
Malie index and set exports
    -> immutable data/raw/malie JSON files plus SHA-256 manifest
    -> validation and normalization
    -> data/card_catalog.sqlite3
    -> private FastAPI service on 127.0.0.1:8770
```

The downloaded raw files and generated database intentionally stay local and are ignored by Git. Every imported card retains its source URL, source record ID, raw-record position, source-file hash, download time, and import time, so the catalog can be audited and rebuilt. Malie's alternate-art/finish records become variants of one canonical set-and-number card instead of duplicate cards.

The canonical catalog contains no user quantities or collection records. Personal quantities are stored separately in `user_data/inventory.sqlite3` and reference stable canonical card IDs, keeping permanent inventory separate from rebuildable reference data.

### Update and run

- Double-click `tools\check_card_updates.bat` to compare the local manifest with Malie's current English export index without changing local data.
- Double-click `tools\update_card_database.bat` to preserve new/changed raw exports and rebuild the affected catalog data.
- Double-click `tools\run_card_api.bat`, then open `http://127.0.0.1:8770/docs` for the interactive local API documentation.

Equivalent command-line operations are:

```powershell
python -m card_api update
python -m card_api update --download
python -m card_api import
python -m card_api sync
python -m card_api serve
```

Initial endpoints are:

- `GET /cards` with optional `set_code`, `number`, `name`, and pagination filters
- `GET /cards/search?q=...`
- `GET /cards/{id}` with text, attacks, images, variants, and provenance
- `GET /sets`
- `GET /sets/{id}/cards`

For example, `/cards?set_code=SSP&number=075` returns Smoochum, while `/cards?set_code=ASC&number=162` returns Team Rocket's Kangaskhan ex from Ascended Heroes. The scanner uses this same local catalog for its match preview without changing the literal OCR evidence.

## Iteration history

- **Iteration 1 — Tesseract proof of concept:** Read selected card-footer images and immediately attempted card lookup.
- **Iteration 2 — Conservative card matching:** Preserved multiple OCR candidates and required review for conflicts, but still focused too heavily on interpreting imperfect readings.
- **Iteration 3 — OCR-only RapidOCR reader:** Replaced Tesseract as the primary reader, removed API/catalog work from the live scan, preserved literal text and leading zeroes, and separated detected letters from detected numbers.
- **Iteration 4 — Automatic OCR on selection:** Releasing a valid drag selection starts OCR immediately. The Rescan Selection button remains available for repeating the same crop.
- **Iteration 5 — Labeled OCR benchmark:** Saves the exact selected crop, raw OCR, confidence, all RapidOCR treatment readings, original detected groups, and user-corrected groups. It supports still-image upload and a live webcam session with a fixed card guide and reusable text selection. The browser checks that it is connected to the matching server before allowing scans.
- **Iteration 6 — Instant local catalog match:** Preserved the Iteration 5 OCR behavior and evidence, then automatically checked a complete detected set code and card number against the local Malie catalog. No internet fallback was used, and a conflicting printed total required review.
- **Iteration 7 — Confirmed local inventory:** Added a separate permanent SQLite inventory, exact-match-only additions, visible quantity, and an auditable undo. Catalog rebuilds cannot overwrite personal quantities.
- **Iteration 8 — Batch inventory quantities:** Added a numeric quantity input from 1 to 99. One button press records the entire batch as one history event, and Undo removes that whole batch.
- **Iteration 9 — Quick inventory intake:** Moves the exact card match, image, current quantity, batch input, Add, and Undo directly below the OCR result so routine inventory intake does not require scrolling past correction controls.
- **Iteration 10 — Visual inventory views:** Preserves Malie card category, Trainer/Energy subtype, and elemental types in the canonical catalog. Adds a read-only collection page with card images and alternate views by name, set/collector number, card category, subtype, or elemental type.
- **Iteration 11 — Complete type view:** Keeps every Pokemon elemental group first, then shows Item, Supporter, Tool, Stadium, Basic Energy, and Special Energy as separate groups at the end of the same view.
- **Iteration 12 — Inventory regulation marks:** Exposes each owned card's canonical regulation mark through the read-only inventory endpoint and displays it on every collection tile, laying the foundation for later regulation-mark searching and filtering.
- **Iteration 13 — Light and dark themes:** Adds a shared theme control to the scanner and collection pages, follows the system preference initially, and remembers a manual light/dark selection in the browser.
- **Iteration 14 — Timed scan diagnostics:** Automatically records client total time, server time, OCR time, attempted treatments, parsed fields, and timeout status for every scan. OCR has a 10-second budget so difficult fallbacks return available evidence instead of searching indefinitely.
- **Iteration 15 — Dark set badge recovery:** Recovers tiny inverse-color set badges such as BLK and WHT when OCR changes exactly one letter and only one local card satisfies the repaired code, number, and printed total. Missing or ambiguous codes remain unmatched.
- **Iteration 16 — Partial set badge recovery:** Handles inverse-color badges such as TEF when OCR retains only the leading one or two set-code letters. Recovery requires both printed numbers and exactly one compatible local card; a completely missing or ambiguous code remains unmatched.
- **Iteration 17 — Premium digital binder:** Rebuilds the read-only inventory as an image-first desktop collection app with live owned-category counts, independent organization and filtering, search, adaptive sorting, recently added ordering, responsive binder grids, and an in-place card detail drawer. Duplicate printings remain one tile with a quantity badge.
- **Iteration 18 — Search-first collection intake (current):** Makes local catalog search the primary entry method while preserving Scan and Collection. The opening page shows no catalog cards until the user chooses at least one search option and presses Enter or **Search cards**. Search combines card name, set name/code, collector number, set, format, and card type, including an ACE SPEC filter. Standard currently includes regulation marks H, I, and J; Expanded includes every English card in the local catalog. Every exact canonical row shows its image and current owned quantity with large decrement/increment controls and direct quantity editing. Collection includes a dedicated ACE SPEC view while those cards remain available under their normal Item, Tool, Stadium, or Special Energy categories. Collection artwork now uses a bounded near-screen loading queue, visible loading placeholders, request timeouts, and two retries so intermittent CDN delays do not leave random blank cards.

The launcher preloads RapidOCR before opening the scanner. The operational reader stops after the first high-confidence treatment only when its set code, card number, and any printed total resolve to one exact local card. Non-matches automatically continue through the remaining treatments. The page keeps both total scan time and server OCR time visible after every scan and disables **Next card** until the current reading is complete.

Future material changes should advance the iteration number and add one short entry here.

## Legacy webcam scanner (dormant)

The webcam interface has been removed from every visible page. Its historical UI and benchmark tooling are retained under `legacy_webcam_scanner/` so the work is not lost. The old `/scan` address now returns to Search; deliberate access remains possible at `/legacy-webcam-scanner` while the collection app is running.

Search is the primary intake method in Iteration 18. The page begins with no card results. Enter a name, set name/code, collector number, or combined identifier such as `PRE 011`; or choose a set, format, or card type. ACE SPEC is available as a dedicated card-type filter without replacing a card's underlying Item, Tool, Stadium, or Special Energy category. Active choices appear as removable filter chips, and **Reset filters** restores the default Standard-only state. Press Enter or **Search cards** to submit—typing, changing filters, and removing chips do not automatically reveal cards. Standard currently means regulation marks H, I, or J, while Expanded searches every English card in the local catalog. Each result is one immutable English catalog printing. Click its artwork for a full-screen inspection view; its quantity controls save directly to the separate inventory database without changing the catalog.

### Webcam workflow

1. Click **Start camera**, choose the camera if more than one is connected, and align the taped card position with the on-screen guide.
2. Slide in a card and click **Capture frame**. The live view freezes without uploading the frame anywhere.
3. The scanner automatically crops only the small bottom-left identifier box containing values such as `SSP 075/191`; everything else on the card is discarded before OCR.
4. Leave **Reuse the fixed bottom-left number box** checked. Correct the fields to what is actually printed and click **Save OCR reading**. Save even a complete no-read.
5. Click **Next card**. Future captured frames reuse the same small box and start OCR automatically.
6. If the taped alignment needs correction, drag a replacement box on one captured frame. That adjusted position is reused for later cards.
7. Click **Stop camera** before leaving the scanner. Closing the page also stops every camera track.

### Still-photo workflow

1. Click **Or choose photo** and open a clear, full-resolution image.
2. Drag a tight rectangle around the letters and numbers you want read.
3. Release the pointer. OCR starts automatically. Use **Rescan Selection** to repeat the crop.
4. Correct the fields and click **Save OCR reading**.

Manually saved correction rows are stored in `legacy_webcam_scanner/evidence/ocr_reads_it18.csv`. Every scan also adds an automatic timing row to `legacy_webcam_scanner/evidence/scan_performance_it18.csv`; no Save button is required for that diagnostic log. Webcam filenames begin with `webcam_`, and every new exact OCR crop is stored under `legacy_webcam_scanner/evidence/benchmark_crops/iteration_18`. Earlier iteration files remain untouched as OCR evidence.

The scanner displays and stores the literal OCR result first. It then separates the letters and digit groups into editable fields. A unique one-letter repair or partial-code recovery may be used for exact local matching, but never changes the retained literal OCR. Every scan gets a unique ID. Its exact crop is stored under `legacy_webcam_scanner/evidence/benchmark_crops/iteration_18`, while the correction CSV keeps both the untouched OCR result and your corrected labels. The automatic performance CSV records the timings and treatments for every attempt, including scans you do not manually save.

For a footer such as `H SSP en 075/191`, the untouched literal OCR is retained for benchmarking. Four editable fields separately show `H` (regulation mark), `SSP` (set code), `075` (card number), and `191` (set total). An exact standalone `en` language marker is discarded from the usable fields.

RapidOCR is the required primary reader for the webcam workflow. The scanner health check blocks new scans instead of silently collecting low-quality Tesseract-only results when RapidOCR is missing. Joined language reads such as `MEGEN` are separated into the known three-letter set code `MEG` plus the discarded language suffix, while the untouched OCR remains in the benchmark evidence.

### Card lookup preview

When OCR reads both a set code and card number, the scanner immediately checks `data/card_catalog.sqlite3` and shows the exact local match. Correct either field and click **Find this card** to check again. There is no internet fallback. Exact matches show the card name, set, number, image, and current inventory quantity; a conflicting printed total is marked **Review**.

### Local inventory

Inventory is never changed merely because OCR found a card. **Add copies to collection** is enabled only for one exact, conflict-free local catalog match. Choose a whole-number quantity from 1 to 99; pressing the button makes the server validate both the card and quantity again before recording the canonical card ID. No-match, ambiguous, review, and invalid-quantity requests are rejected by the server even if a browser request is sent manually.

The mutable database lives at `user_data/inventory.sqlite3`, outside the rebuildable Malie catalog. Each batch records one immutable history event with the optional originating scan ID. **Undo last batch** removes that entire batch but retains a compensating history event, so mistakes remain auditable. Before any real quantity change, the app creates and integrity-checks a timestamped SQLite snapshot in `user_data/backups/`. Git intentionally ignores both the personal database and these backups.

Open **My Collection** to view the digital binder. The persistent sidebar filters the same owned records by Pokemon type, Trainer subtype, Energy kind, or ACE SPEC status, while **Typing**, **A–Z**, and **Set** independently determine how those records are organized. Search matches card names, set names/codes, collector numbers, categories, and ACE SPEC. Set and sort controls narrow or reorder the current view. **Recently added** uses the permanent inventory timestamp. Click card artwork for the full-screen inspection view, or click its name/details to open the quantity drawer without losing the binder position. The detail drawer can set an exact quantity, confirms before removing the final copy, and saves through the same audited inventory endpoint used by catalog search.

The Collection toolbar provides **CSV** and **JSON** exports. Both use the versioned `pokemon-card-collection` schema and preserve immutable canonical card IDs, exact quantities, readable card identity fields, and inventory timestamps. JSON is the canonical transfer/restore representation because it retains structured fields and export metadata. CSV contains the same card records in an Excel-friendly UTF-8 table for sorting or editing.

Use **Import** beside those export buttons to select either format. Import is always preview-first and shows summary counts for additions, quantity changes, removals, unchanged cards, and the resulting total. Only affected cards are listed, with search, change-type filtering, and 75-row pagination for thousand-card collections. **Update listed cards** changes only rows present in the file. **Restore / replace** makes the collection exactly match the file and therefore previews cards that would be removed. Applying requires confirmation, revalidates every canonical ID against the local English catalog, rejects stale previews if the collection changed, and performs all edits in one transaction after creating one integrity-checked database backup. Normal one-card corrections remain available in real time through the collection detail drawer.

- `GET /inventory/export.json` downloads the structured collection export.
- `GET /inventory/export.csv` downloads the spreadsheet-compatible collection export.
- `POST /inventory/import/preview` validates and compares an export without changing inventory.
- `POST /inventory/import/apply` revalidates and applies the confirmed preview.

### Saved deck library

The **Deck Check** page includes an optional saved deck library. After a clean deck list has been checked, give it a name and select **Save to deck library**. Opening a saved deck restores the original list and immediately checks it against the collection as it exists now, so readiness is never treated as a permanent or potentially stale result. Saved decks can be renamed or removed from the library.

### Optional physical locations

The Collection sidebar can organize owned copies into optional locations such as **Deck Box 1**, **Trade Binder**, or **Shelf**. Existing and newly added cards begin in the virtual **Unassigned** location. Open a card's detail drawer to assign any number of its owned copies to one or more locations. **All cards** always shows the complete collection; selecting a location shows only its assigned copies and uses that location's quantities on the card badges.

Location assignments never create, remove, or reserve collection records. The combined quantity assigned across locations cannot exceed the card's total owned quantity, and the total owned quantity cannot be lowered below the number already assigned. Removing a location returns all of its assigned copies to **Unassigned** without changing collection totals. Location edits create the same automatic SQLite backups as other collection edits.

- `GET /inventory/locations` lists active locations and aggregate counts.
- `POST /inventory/locations/create` creates an optional location.
- `POST /inventory/locations/rename` renames a location.
- `POST /inventory/locations/remove` archives a location and releases its assignments.
- `POST /inventory/locations/set-quantity` changes one card's quantity in one location.

Decks are stored separately in `user_data/decks.sqlite3`. Saving, opening, renaming, or removing a deck never changes, reserves, or moves inventory quantities. Removed decks are archived internally instead of having their stored list immediately destroyed. Both personal SQLite databases remain local and are ignored by Git.

- `GET /decks` lists active saved decks.
- `POST /decks/save` saves a validated deck list.
- `POST /decks/rename` changes only the saved deck name.
- `POST /decks/remove` archives a saved deck without changing inventory.

The 26 saved webcam crops were re-run offline after installing RapidOCR and adding joined-language cleanup. Exact set-code reads improved from 1/26 to 21/26, card-number reads from 3/26 to 25/26, and set-total reads from 4/25 to 23/25. Regulation marks remained unreliable at 1/20, so that field stays editable and must not be used for automatic card identity or sorting.

For the first benchmark, scan 15–25 representative images: clear, blurry, reflective, tilted, promo, and leading-zero examples. Existing full-resolution photos are fine and make comparisons between iterations more reliable; rescan only when you need conditions not represented in those photos. Keep this completed CSV as the Iteration 5 baseline.

## Photo setup that matters

- Fill most of the photo with the 2.5 × 3.5 inch card; do not photograph it from across the room.
- Use the phone's highest-resolution normal camera mode, not digital zoom.
- Keep the camera square to the card and tap the tiny footer to focus.
- Use bright, diffuse light. Avoid glare from sleeves and overhead bulbs.
- For a webcam, use one capable of close focus (or add a macro lens). The tiny text should be at least roughly 20–30 pixels tall in the original image for dependable OCR.

## Card lookup

Card lookup is connected only after literal OCR finishes. A complete detected set code and card number trigger one exact local-catalog query; the OCR result and all benchmark evidence remain unchanged. A displayed match is not proof that OCR was correct, so compare its name and image with the physical card. Missing matches do not guess, and printed-total conflicts require review.

A card database API can identify or validate a card only after the printed characters have been read; it cannot make pixels clearer or improve OCR. If the labeled Iteration 5 benchmark shows RapidOCR is not accurate enough, the same saved crops can be tested against a dedicated cloud OCR service as a separate, controlled comparison. That would require credentials and would upload those selected crops to the provider.

## Windows camera note

The intermittent Windows Camera `MediaCaptureFailedEvent` error `0xC00D36D5` has so far cleared only after fully power-cycling the computer. Close Windows Camera, Teams, Zoom, Discord, OBS, and other camera-using programs before starting this scanner. Use **Stop camera** when finished. The scanner stops every media track on Stop, camera errors, page close, and page navigation so another application can claim the device.

## Intended next steps

A later visual inventory can join quantities from `user_data/inventory.sqlite3` to names and images in the canonical catalog without changing stored holdings. Condition, finish, language, notes, and broader inventory browsing can be added as separate inventory features. Automatic card-edge/footer detection, calibrated confidence, and continuous sorting/output integration can also continue independently. The current version deliberately captures one webcam frame per card instead of running OCR continuously on video.
