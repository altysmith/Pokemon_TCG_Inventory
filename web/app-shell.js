/* Shared app navigation and artwork presentation; no collection data is changed. */
(() => {
  const destinations = [['/inventory', 'Collection', '▦'], ['/', 'Search', '⌕'], ['/needed', 'Need Cards', '◇'], ['/deck', 'Decks', '▤']];
  const nav = document.createElement('nav');
  nav.className = 'app-bottom-nav';
  nav.setAttribute('aria-label', 'Main navigation');
  for (const [href, label, icon] of destinations) {
    const link = document.createElement('a');
    link.href = href;
    const symbol = document.createElement('span');
    symbol.setAttribute('aria-hidden', 'true');
    symbol.textContent = icon;
    link.append(symbol, document.createTextNode(label));
    if (location.pathname.replace(/\/$/, '') === href.replace(/\/$/, '')) link.setAttribute('aria-current', 'page');
    nav.append(link);
  }
  document.body.append(nav);
  document.body.classList.add('has-app-nav');

  const artSelector = '.binder-card-art, .catalog-result-art, .needed-card-art, .deck-gallery-art, .deck-builder-preview-art, .deck-editor-entry-art, .deck-editor-result-art, .deck-assignment-option-art';
  function prepareArt(art) {
    if (art.querySelector(':scope > .card-image-fallback')) return;
    const fallback = document.createElement('span');
    fallback.className = 'card-image-fallback';
    // Artwork buttons and adjacent card titles already supply the accessible name.
    fallback.setAttribute('aria-hidden', 'true');
    const icon = document.createElement('span'); icon.className = 'card-image-icon'; icon.textContent = '◇';
    const label = document.createElement('span'); label.textContent = 'Image unavailable';
    fallback.append(icon, label); art.append(fallback);
  }
  function prepareImage(image) {
    if (image.dataset.shellImage) return;
    image.dataset.shellImage = 'true';
    let art = image.closest(artSelector);
    if (!art && image.matches('.deck-featured-art')) {
      art = document.createElement('span'); art.className = 'deck-featured-frame';
      image.before(art); art.append(image);
    }
    if (!art) return;
    prepareArt(art);
    image.addEventListener('error', () => art.classList.add('image-missing'));
    image.addEventListener('load', () => art.classList.remove('image-missing'));
    if ((!image.getAttribute('src') && !image.dataset.imageUrl) || (image.complete && image.getAttribute('src') && !image.naturalWidth)) art.classList.add('image-missing');
  }
  function scan(root) {
    if (!(root instanceof Element)) return;
    if (root.matches(artSelector)) prepareArt(root);
    root.querySelectorAll(artSelector).forEach(prepareArt);
    if (root.matches('img')) prepareImage(root);
    root.querySelectorAll('img').forEach(prepareImage);
  }
  scan(document.body);
  new MutationObserver(records => {
    for (const record of records) for (const node of record.addedNodes) scan(node);
  }).observe(document.body, {childList: true, subtree: true});

  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const menu = document.activeElement?.closest('.deck-library-menu[open]');
    if (menu) { menu.open = false; menu.querySelector('summary').focus(); }
  });
  document.addEventListener('click', event => {
    document.querySelectorAll('.deck-library-menu[open]').forEach(menu => {
      if (!menu.contains(event.target)) menu.open = false;
    });
  });
})();
