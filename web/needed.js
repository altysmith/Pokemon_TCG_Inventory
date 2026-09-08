const neededTotal = document.querySelector('#needed_total');
const neededUnique = document.querySelector('#needed_unique');
const neededDecks = document.querySelector('#needed_decks');
const neededStatus = document.querySelector('#needed_status');
const neededGroups = document.querySelector('#needed_groups');
const neededRefresh = document.querySelector('#needed_refresh');

let neededItems = [];

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function tcgplayerSearchUrl(card) {
  const searchTerms = [card.name, card.set_code, card.number].filter(Boolean).join(' ');
  const parameters = new URLSearchParams({
    productLineName: 'pokemon',
    productTypeName: 'Cards',
    q: searchTerms,
    view: 'grid',
  });
  return `https://www.tcgplayer.com/search/pokemon/product?${parameters.toString()}`;
}

function printingLabel(card) {
  return card.set_code && card.number ? `${card.set_code} · ${card.number}` : 'Any printing';
}

function neededCard(card, index) {
  const deckLabels = card.decks.map(deck => `
    <li><a href="/deck?deck=${deck.id}">${escapeHtml(deck.name)}</a><b>×${deck.quantity}</b></li>
  `).join('');
  return `
    <article class="needed-card">
      <button class="needed-card-art ${card.image_url ? '' : 'image-missing'}" type="button" data-needed-index="${index}" aria-label="Inspect ${escapeHtml(card.name)}">
        ${card.image_url ? `<img src="${escapeHtml(card.image_url)}" alt="${escapeHtml(card.name)} card" loading="lazy">` : ''}
        <strong>Need ${card.quantity}</strong>
      </button>
      <div class="needed-card-copy">
        <small>${escapeHtml(card.category)}</small>
        <h3>${escapeHtml(card.name)}</h3>
        <p>${escapeHtml(printingLabel(card))}</p>
        <ul aria-label="Needed by deck">${deckLabels}</ul>
        <a class="needed-buy-link" href="${escapeHtml(tcgplayerSearchUrl(card))}" target="_blank" rel="noopener noreferrer">
          Find on TCGplayer <span aria-hidden="true">↗</span>
        </a>
      </div>
    </article>`;
}

function neededGroup(title, section, items) {
  const indexed = items
    .map((card, index) => ({card, index}))
    .filter(entry => entry.card.deck_section === section);
  if (!indexed.length) return '';
  const total = indexed.reduce((sum, entry) => sum + entry.card.quantity, 0);
  return `
    <section class="needed-group">
      <header><h2>${title}</h2><span>${total} ${total === 1 ? 'copy' : 'copies'}</span></header>
      <div>${indexed.map(entry => neededCard(entry.card, entry.index)).join('')}</div>
    </section>`;
}

function renderNeededCards(data) {
  neededItems = data.items || [];
  neededTotal.textContent = data.summary.total_copies;
  neededUnique.textContent = data.summary.unique_cards;
  neededDecks.textContent = data.summary.decks_with_needs;
  if (!neededItems.length) {
    neededGroups.innerHTML = `
      <div class="needed-empty">
        <strong>Your saved decks are covered.</strong>
        <p>No cards are currently needed.</p>
      </div>`;
    return;
  }
  neededGroups.innerHTML = [
    neededGroup('Pokémon', 'pokemon', neededItems),
    neededGroup('Trainer', 'trainer', neededItems),
    neededGroup('Energy', 'energy', neededItems),
  ].join('');
  document.querySelectorAll('[data-needed-index]').forEach(button => {
    button.addEventListener('click', () => {
      const card = neededItems[Number(button.dataset.neededIndex)];
      if (card?.image_url) window.CardInspector?.open?.(card, button);
    });
  });
}

async function loadNeededCards() {
  neededRefresh.disabled = true;
  neededStatus.textContent = 'Refreshing assignments and checking every saved deck…';
  try {
    const response = await fetch('/decks/needed');
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'The needed-card list could not be loaded.');
    renderNeededCards(data);
    neededStatus.textContent = data.summary.saved_decks
      ? `Current shortages across ${data.summary.saved_decks} saved ${data.summary.saved_decks === 1 ? 'deck' : 'decks'}. Inventory quantities and locations were not changed.`
      : 'Save a deck first to build your shopping list.';
  } catch (error) {
    neededStatus.textContent = error.message;
    neededGroups.innerHTML = '';
  } finally {
    neededRefresh.disabled = false;
  }
}

neededRefresh.addEventListener('click', () => void loadNeededCards());
void loadNeededCards();
