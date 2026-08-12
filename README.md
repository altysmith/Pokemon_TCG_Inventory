# Tiny Card Text Scanner

**Current build: Iteration 5 — Labeled OCR benchmark**

This local browser app reads the literal text in a manually selected part of a webcam frame or still image. RapidOCR is the primary general-purpose reader; Tesseract is used only if RapidOCR finds no text. The live reader does not parse or identify cards and does not contact an API. Images stay on this computer.

## Run it

Double-click **`run_scanner.bat`**. It starts the private local scanner and opens `http://127.0.0.1:8766/` in your normal browser. Keep the small command window open while scanning; close it when finished.

RapidOCR, ONNX Runtime, Tesseract, and the required Python runtime are installed on this machine. `requirements.txt` is included for installing the project on another computer.

## Local card database and API

This repository now contains two isolated components: the working Iteration 5 scanner and a new `card_api` catalog service. Keeping them in one repository makes their eventual connection straightforward, while the separate code paths and database files protect the working scanner from catalog changes.

The catalog uses [Malie.io's formatted TCGL exports](https://malie.io/static/index.html) as its primary source. Its pipeline is:

```text
Malie index and set exports
    -> immutable data/raw/malie JSON files plus SHA-256 manifest
    -> validation and normalization
    -> data/card_catalog.sqlite3
    -> private FastAPI service on 127.0.0.1:8770
```

The downloaded raw files and generated database intentionally stay local and are ignored by Git. Every imported card retains its source URL, source record ID, raw-record position, source-file hash, download time, and import time, so the catalog can be audited and rebuilt. Malie's alternate-art/finish records become variants of one canonical set-and-number card instead of duplicate cards.

The canonical catalog contains no user quantities or collection records. A future collection database will reference the stable canonical card ID, keeping personal inventory separate from rebuildable reference data.

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

For example, `/cards?set_code=SSP&number=075` returns Smoochum, while `/cards?set_code=ASC&number=162` returns Team Rocket's Kangaskhan ex from Ascended Heroes. A future scanner integration will send its reviewed set code and card number to this local endpoint. No OCR behavior is changed in this database iteration.

## Iteration history

- **Iteration 1 — Tesseract proof of concept:** Read selected card-footer images and immediately attempted card lookup.
- **Iteration 2 — Conservative card matching:** Preserved multiple OCR candidates and required review for conflicts, but still focused too heavily on interpreting imperfect readings.
- **Iteration 3 — OCR-only RapidOCR reader:** Replaced Tesseract as the primary reader, removed API/catalog work from the live scan, preserved literal text and leading zeroes, and separated detected letters from detected numbers.
- **Iteration 4 — Automatic OCR on selection:** Releasing a valid drag selection starts OCR immediately. The Rescan Selection button remains available for repeating the same crop.
- **Iteration 5 — Labeled OCR benchmark (current):** Saves the exact selected crop, raw OCR, confidence, all RapidOCR treatment readings, original detected groups, and user-corrected groups. It supports still-image upload and a live webcam session with a fixed card guide and reusable text selection. The browser checks that it is connected to the Iteration 5 server before allowing scans.

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

Rows from both workflows are stored in `ocr_reads_it5.csv`. Webcam filenames begin with `webcam_`; every exact OCR crop is stored under `benchmark_crops/iteration_5`.

The scanner displays the literal OCR result first. It then separates the letters and digit groups into editable fields without correcting them against a known card list. Every scan gets a unique ID. Its exact crop is stored under `benchmark_crops/iteration_5`, while the CSV keeps both the untouched OCR result and your corrected labels. This makes wrong reads, partial reads, and blank reads measurable instead of hiding them.

For a footer such as `H SSP en 075/191`, the untouched literal OCR is retained for benchmarking. Four editable fields separately show `H` (regulation mark), `SSP` (set code), `075` (card number), and `191` (set total). An exact standalone `en` language marker is discarded from the usable fields.

RapidOCR is the required primary reader for the webcam workflow. The scanner health check blocks new scans instead of silently collecting low-quality Tesseract-only results when RapidOCR is missing. Joined language reads such as `MEGEN` are separated into the known three-letter set code `MEG` plus the discarded language suffix, while the untouched OCR remains in the benchmark evidence.

### Card lookup preview

After OCR, correct the set code and card number, then click **Find this card**. This project checks its own `scanner_data.sqlite3` cache first and uses TCGdex followed by the Pokemon TCG API only when the card is not cached. Exact matches show the card name, set, number, and image for review. A conflicting printed total is marked **Review**. This preview never adds a card to inventory, and it has no connection to the older TKD Card Inventory application.

The 26 saved webcam crops were re-run offline after installing RapidOCR and adding joined-language cleanup. Exact set-code reads improved from 1/26 to 21/26, card-number reads from 3/26 to 25/26, and set-total reads from 4/25 to 23/25. Regulation marks remained unreliable at 1/20, so that field stays editable and must not be used for automatic card identity or sorting.

For the first benchmark, scan 15–25 representative images: clear, blurry, reflective, tilted, promo, and leading-zero examples. Existing full-resolution photos are fine and make comparisons between iterations more reliable; rescan only when you need conditions not represented in those photos. Keep this completed CSV as the Iteration 5 baseline.

## Photo setup that matters

- Fill most of the photo with the 2.5 × 3.5 inch card; do not photograph it from across the room.
- Use the phone's highest-resolution normal camera mode, not digital zoom.
- Keep the camera square to the card and tap the tiny footer to focus.
- Use bright, diffuse light. Avoid glare from sleeves and overhead bulbs.
- For a webcam, use one capable of close focus (or add a macro lens). The tiny text should be at least roughly 20–30 pixels tall in the original image for dependable OCR.

## Card lookup

Card lookup is deliberately disconnected from the live reader. The existing lookup module remains available for a future separate processing step, but scanning an image never invokes it.

A card database API can identify or validate a card only after the printed characters have been read; it cannot make pixels clearer or improve OCR. If the labeled Iteration 5 benchmark shows RapidOCR is not accurate enough, the same saved crops can be tested against a dedicated cloud OCR service as a separate, controlled comparison. That would require credentials and would upload those selected crops to the provider.

## Windows camera note

The intermittent Windows Camera `MediaCaptureFailedEvent` error `0xC00D36D5` has so far cleared only after fully power-cycling the computer. Close Windows Camera, Teams, Zoom, Discord, OBS, and other camera-using programs before starting this scanner. Use **Stop camera** when finished. The scanner stops every media track on Stop, camera errors, page close, and page navigation so another application can claim the device.

## Intended next steps

After collecting more labeled examples, a future version can add automatic card-edge/footer detection, calibrated confidence, and continuous sorting/output integration. The current version deliberately captures one webcam frame per card instead of running OCR continuously on video.
