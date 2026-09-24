from pathlib import Path
s=Path('tmp/deploy-collection-shortages.py').read_text().replace('collection-shortages-20260919','compact-allocation-badges-20260919').replace("files=['web/inventory.js','web/deck.js','web/style.css']", "files=['deck_allocations.py','web/inventory.js','web/style.css']")
Path('tmp/deploy-compact-badges.py').write_text(s)
