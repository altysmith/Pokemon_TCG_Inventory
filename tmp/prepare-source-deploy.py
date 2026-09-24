from pathlib import Path
s=Path('tmp/deploy-collection-presentation.py').read_text(encoding='utf-8').replace('collection-deck-presentation-20260919','deck-source-choice-20260919')
a=s.index('files=');b=s.index('\nfor name,digest',a)
s=s[:a]+"files=['app.py','deck_allocations.py','web/deck.js','web/style.css']\nexpected={'app.py':'507a5bcdb66e96107570c84236b60686a15eeda5c05f20c8a5ad89052c5dd017','deck_allocations.py':'20d9df7d93f39161773fe74001f83d050919e537b942144a11f1634151478750'}"+s[b:]
s=s.replace('verified 8 files','verified 4 files')
Path('tmp/deploy-deck-source-choice.py').write_text(s,encoding='utf-8')
