from pathlib import Path
s=Path('tmp/deploy-deck-source-choice.py').read_text().replace('deck-source-choice-20260919','collection-shortages-20260919')
a=s.index('files=');b=s.index('\nfor name,digest',a)
s=s[:a]+"files=['web/inventory.js','web/deck.js','web/style.css']\nexpected={}"+s[b:]
s=s.replace('verified 4 files','verified 3 files')
Path('tmp/deploy-collection-shortages.py').write_text(s)
