from pathlib import Path
s=Path('tmp/deploy-deck-allocations.py').read_text(encoding='utf-8')
s=s.replace('deck-allocations-20260919','collection-deck-presentation-20260919')
s=s.replace("files=['app.py','deck_checker.py','deck_allocations.py','web/deck.js','web/style.css']", "files=['app.py','saved_decks.py','web/app-shell.js','web/deck.html','web/deck.js','web/inventory.html','web/inventory.js','web/style.css']")
a=s.index('expected=');b=s.index('\nfor name,digest',a)
s=s[:a]+"expected={'app.py':'1e7db876a9c68141c55b06b0f68b479ce846b3b5c20e22ea465c85582f663f7f','saved_decks.py':'ed86c3d48df328a2a1f33b52269b9938aaf34a0406a9f95f08053dd73c1f2c2b'}"+s[b:]
s=s.replace("assert not (root/'deck_allocations.py').exists(), 'New module already exists; stopping'\n",'').replace('verified 5 files','verified 8 files')
Path('tmp/deploy-collection-presentation.py').write_text(s,encoding='utf-8')
