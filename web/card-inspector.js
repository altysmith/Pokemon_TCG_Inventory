(() => {
  const overlay = document.createElement('div');
  overlay.className = 'card-inspector';
  overlay.hidden = true;
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-label', 'Large card artwork');

  const panel = document.createElement('div');
  panel.className = 'card-inspector-panel';
  const closeButton = document.createElement('button');
  closeButton.className = 'card-inspector-close';
  closeButton.type = 'button';
  closeButton.setAttribute('aria-label', 'Close large card view');
  closeButton.textContent = 'Close';
  const image = document.createElement('img');
  image.className = 'card-inspector-image';
  const caption = document.createElement('p');
  caption.className = 'card-inspector-caption';
  panel.append(closeButton, image, caption);
  overlay.append(panel);
  document.body.append(overlay);

  let priorFocus = null;

  function close() {
    if (overlay.hidden) return;
    overlay.hidden = true;
    image.removeAttribute('src');
    document.body.classList.remove('card-inspector-open');
    priorFocus?.focus?.();
  }

  function open(card, trigger = document.activeElement) {
    if (!card?.image_url) return;
    priorFocus = trigger;
    image.src = card.image_url;
    image.alt = `${card.name || 'Selected card'} card artwork`;
    const number = card.printed_total ? `${card.number}/${card.printed_total}` : card.number || '';
    caption.textContent = [card.name, card.set_code, number].filter(Boolean).join('  |  ');
    overlay.hidden = false;
    document.body.classList.add('card-inspector-open');
    closeButton.focus();
  }

  closeButton.addEventListener('click', close);
  overlay.addEventListener('click', (event) => { if (event.target === overlay) close(); });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !overlay.hidden) {
      event.preventDefault();
      close();
    }
  });

  window.CardInspector = {open, close};
})();
