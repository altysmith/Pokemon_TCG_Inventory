from pathlib import Path
s=Path('tmp/check-deck-allocation.cjs').read_text()
s=s.replace("includes('Gardevoir')", "includes('Zoroark')").replace('data.source_deck_id,2','data.source_deck_id,3')
s=s.replace("{deck_id:2,deck_name:'Gardevoir',card_id:'stamp',quantity:1}","{deck_id:2,deck_name:'Gardevoir',card_id:'stamp',quantity:1},{deck_id:3,deck_name:'Zoroark',card_id:'stamp',quantity:1}")
s=s.replace('[data-allocation-source="0"]','[data-allocation-source="1"]')
s=s.replace('warning, cancel, transfer, refreshed status','two sources, cancel, chosen second source, refreshed status')
Path('tmp/check-source-choice.cjs').write_text(s)
