# Legacy webcam scanner

The webcam experiment is intentionally absent from the normal collection,
catalog search, and deck-checking navigation. Its browser interface and OCR
benchmark are retained here so the work can be restored or studied later.

When the local collection app is running, the dormant interface is available
only at `http://127.0.0.1:8766/legacy-webcam-scanner`.

The shared server still contains the legacy scanner endpoints, and the OCR
library remains in `card_scanner/` because those pieces are covered by the
historical regression tests. Nothing in the normal user interface calls them.
