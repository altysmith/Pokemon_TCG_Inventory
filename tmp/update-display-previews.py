from pathlib import Path
for filename in ['web/deck.js','web/inventory.js']:
 p=Path(filename);s=p.read_text(encoding='utf-8')
 old='try { featured = items.find(x => x.image_url === localStorage.getItem(`deck-featured-${deck.id}`)) || featured; } catch {}'
 new=old+'\n    featured = items.find(x => x.image_url === deck.display_image) || featured;'
 assert old in s;s=s.replace(old,new)
 if filename.endswith('/deck.js'):
  s=s.replace('for (const item of pokemon.filter(x => x.image_url))', 'for (const item of items.filter(x => x.image_url))')
  old="select.addEventListener('change', () => { image.src = select.value; image.hidden = false; image.alt = select.selectedOptions[0].textContent; try { localStorage.setItem(`deck-featured-${deck.id}`, select.value); } catch {} });"
  new="""select.addEventListener('change', async () => {
        select.disabled = true;
        try {
          await requestJson('/decks/display-card', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id: deck.id, display_image: select.value})});
          deck.display_image = select.value;
          image.src = select.value; image.hidden = false; image.alt = select.selectedOptions[0].textContent;
        } catch (error) { select.value = deck.display_image || featured?.image_url || ''; setLibraryStatus(error.message, 'error'); }
        finally { select.disabled = false; }
      });"""
  assert old in s;s=s.replace(old,new).replace('if (pokemon.some(x => x.image_url)) {','if (items.some(x => x.image_url)) {')
 p.write_text(s,encoding='utf-8')
