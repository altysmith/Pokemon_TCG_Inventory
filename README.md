# Tiny Card Text Scanner

**Current build: Iteration 13 — Light and dark themes**

This local browser app reads the literal text in a manually selected part of a webcam frame or still image. RapidOCR is the primary general-purpose reader; Tesseract is used only if RapidOCR finds no text. After reading, complete set-and-number fields are checked against the local catalog. Images stay on this computer, and scanning uses no internet API.

## Run it

Double-click **`run_scanner.bat`**. It starts the private local scanner and opens `http://127.0.0.1:8766/` in your normal browser. Keep the small command window open while scanning; close it when finished.

RapidOCR, ONNX Runtime, Tesseract, and the required Python runtime are installed on this machine. `requirements.txt` is included for installing the project on another computer.

## Local card database and API

This repository contains two isolated components: the webcam scanner and the `card_api` catalog service. They share exact catalog queries while retaining separate code paths and data responsibilities.

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

- Double-click `check_card_updates.bat` to compare the local manifest with Malie's current English export index without changing local data.
- Double-click `update_card_database.bat` to preserve new/changed raw exports and rebuild the affected catalog data.
- Double-click `run_card_api.bat`, then open `http://127.0.0.1:8770/docs` for the interactive local API documentation.

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
- **Iteration 13 — Light and dark themes (current):** Adds a shared theme control to the scanner and collection pages, follows the system preference initially, and remembers a manual light/dark selection in the browser.

The launcher preloads RapidOCR before opening the scanner. The operational reader stops after the first high-confidence treatment only when its set code, card number, and any printed total resolve to one exact local card. Non-matches automatically continue through the remaining treatments. The page keeps both total scan time and server OCR time visible after every scan and disables **Next card** until the current reading is complete.

Future material changes should advance the iteration number and add one short entry here.

## Scan a card

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

New rows from both workflows are stored in `ocr_reads_it13.csv`. Webcam filenames begin with `webcam_`; every new exact OCR crop is stored under `benchmark_crops/iteration_13`. Earlier iteration files remain untouched as OCR evidence.

The scanner displays the literal OCR result first. It then separates the letters and digit groups into editable fields without correcting them against a known card list. Every scan gets a unique ID. Its exact crop is stored under `benchmark_crops/iteration_13`, while the CSV keeps both the untouched OCR result and your corrected labels. This makes wrong reads, partial reads, and blank reads measurable instead of hiding them.

For a footer such as `H SSP en 075/191`, the untouched literal OCR is retained for benchmarking. Four editable fields separately show `H` (regulation mark), `SSP` (set code), `075` (card number), and `191` (set total). An exact standalone `en` language marker is discarded from the usable fields.

RapidOCR is the required primary reader for the webcam workflow. The scanner health check blocks new scans instead of silently collecting low-quality Tesseract-only results when RapidOCR is missing. Joined language reads such as `MEGEN` are separated into the known three-letter set code `MEG` plus the discarded language suffix, while the untouched OCR remains in the benchmark evidence.

### Card lookup preview

When OCR reads both a set code and card number, the scanner immediately checks `data/card_catalog.sqlite3` and shows the exact local match. Correct either field and click **Find this card** to check again. There is no internet fallback. Exact matches show the card name, set, number, image, and current inventory quantity; a conflicting printed total is marked **Review**.

### Local inventory

Inventory is never changed merely because OCR found a card. **Add copies to collection** is enabled only for one exact, conflict-free local catalog match. Choose a whole-number quantity from 1 to 99; pressing the button makes the server validate both the card and quantity again before recording the canonical card ID. No-match, ambiguous, review, and invalid-quantity requests are rejected by the server even if a browser request is sent manually.

The mutable database lives at `user_data/inventory.sqlite3`, outside the rebuildable Malie catalog. Each batch records one immutable history event with the optional originating scan ID. **Undo last batch** removes that entire batch but retains a compensating history event, so mistakes remain auditable. Back up the `user_data` folder whenever you back up the collection; Git intentionally ignores this personal database.

Click **View collection** at the top of the scanner to open the read-only visual inventory. The same holdings can be displayed alphabetically, by set and collector number, by broad card category, by Item/Supporter/Tool/Stadium or Energy subtype, or by Pokemon elemental type. In the elemental view, all Pokemon types appear first, followed by separate Item, Supporter, Tool, Stadium, Basic Energy, and Special Energy groups. These choices only change display order and grouping; they never edit quantities.

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
