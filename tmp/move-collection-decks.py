from pathlib import Path
p=Path('web/inventory.html')
s=p.read_text(encoding='utf-8')
start=s.index('        <section class="binder-location-nav binder-deck-nav"')
end=s.index('        <nav id="category_navigation"',start)
block=s[start:end]
s=s[:start]+s[end:]
pos=s.index('        <button id="recent_button"')
s=s[:pos]+block+s[pos:]
s=s.replace('<select id="saved_deck_sort">','<select id="saved_deck_sort"><option value="custom">Custom order</option>')
p.write_text(s,encoding='utf-8')
