const form = document.querySelector('#deck_form');
const deckList = document.querySelector('#deck_list');
const submitButton = document.querySelector('#deck_submit');
const summary = document.querySelector('#deck_summary');
const statusText = document.querySelector('#deck_status');
const errorsContainer = document.querySelector('#deck_errors');
const resultsContainer = document.querySelector('#deck_results');

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function printingLabel(card) {
  return `${card.set_code || '—'} · ${card.number || '—'}`;
}

function renderSummary(data) {
  const result = data.summary;
  const ready = result.missing_cards === 0 && data.errors.length === 0;
  summary.hidden = false;
  summary.className = `deck-summary ${ready ? 'is-complete' : 'has-missing'}`;
  summary.innerHTML = `
    <div class="deck-summary-verdict">
      <span>${ready ? 'DECK READY' : 'CARDS NEEDED'}</span>
      <strong>${ready ? 'You can build this deck.' : `${result.missing_cards} ${result.missing_cards === 1 ? 'card' : 'cards'} still needed.`}</strong>
    </div>
    <dl>
      <div><dt>Deck</dt><dd>${result.deck_cards}</dd></div>
      <div><dt>Covered</dt><dd>${result.covered_cards}</dd></div>
      <div><dt>Missing</dt><dd>${result.missing_cards}</dd></div>
      <div><dt>Substitutes</dt><dd>${result.possible_substitute_cards || 0}</dd></div>
      <div><dt>Basic Energy ignored</dt><dd>${result.ignored_basic_energy_cards || 0}</dd></div>
      <div><dt>Unique entries</dt><dd>${result.unique_lines}</dd></div>
    </dl>`;
}

function renderErrors(errors) {
  errorsContainer.hidden = errors.length === 0;
  errorsContainer.innerHTML = errors.length ? `
    <h2>Lines needing review</h2>
    ${errors.map(error => `
      <div><strong>Line ${error.line}</strong><span>${escapeHtml(error.message)}</span><code>${escapeHtml(error.text)}</code></div>
    `).join('')}` : '';
}

let renderedDeckItems = [];

function deckGroup(item) {
  if (['pokemon', 'trainer', 'energy'].includes(item.deck_section)) return item.deck_section;
  if (item.category === 'Pokémon') return 'pokemon';
  if (item.status === 'ignored' || item.category.includes('Energy')) return 'energy';
  return 'trainer';
}

function deckItemState(item) {
  if (item.status === 'ready') return 'Ready';
  if (item.status === 'ignored') return 'Ignored';
  if (item.status === 'unresolved') return 'Review';
  return `Need ${item.missing}`;
}

function deckBuilderRow(item, index) {
  const group = deckGroup(item);
  const printing = group === 'pokemon' ? item.set_code : '';
  return `
    <button class="deck-builder-row ${item.status === 'ready' ? 'is-ready' : item.status === 'ignored' ? 'is-ignored' : 'is-needed'}" type="button" data-deck-index="${index}" aria-pressed="false">
      <strong>${item.requested}×</strong>
      <span><em>${escapeHtml(item.name)}</em>${printing ? `<small>${escapeHtml(printing)}</small>` : ''}</span>
      <b>${deckItemState(item)}</b>
    </button>`;
}

function deckBuilderGroup(title, indexedItems) {
  if (!indexedItems.length) return '';
  const count = indexedItems.reduce((total, entry) => total + entry.item.requested, 0);
  return `
    <section class="deck-builder-group">
      <header><h3>${title} <span>(${count})</span></h3></header>
      <div>${indexedItems.map(entry => deckBuilderRow(entry.item, entry.index)).join('')}</div>
    </section>`;
}

function selectDeckItem(index) {
  const item = renderedDeckItems[index];
  const preview = document.querySelector('#deck_builder_preview');
  if (!item || !preview) return;
  document.querySelectorAll('.deck-builder-row').forEach(row => {
    const selected = Number(row.dataset.deckIndex) === index;
    row.classList.toggle('is-selected', selected);
    row.setAttribute('aria-pressed', String(selected));
  });
  const group = deckGroup(item);
  const printing = group === 'pokemon'
    ? printingLabel(item)
    : item.status === 'ignored'
      ? 'Not checked against inventory'
      : 'Any printing may be used';
  preview.innerHTML = `
    <div class="deck-builder-preview-heading">
      <small>${escapeHtml(item.category)}</small>
      <h3>${escapeHtml(item.name)}</h3>
    </div>
    <div class="deck-builder-preview-art ${item.image_url ? '' : 'image-missing'}">
      ${item.image_url ? `<img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.name)}">` : ''}
    </div>
    <dl>
      <div><dt>Deck quantity</dt><dd>${item.requested}</dd></div>
      <div><dt>Printing</dt><dd>${escapeHtml(printing)}</dd></div>
      <div><dt>Inventory</dt><dd class="${item.status === 'ready' ? 'is-ready' : item.status === 'ignored' ? 'is-ignored' : 'is-needed'}">${escapeHtml(deckItemState(item))}</dd></div>
    </dl>`;
}

function renderResults(items, ignoredBasicEnergy = []) {
  if (!items.length && !ignoredBasicEnergy.length) {
    resultsContainer.innerHTML = `
      <div class="deck-empty-check">
        <strong>No inventory check was needed.</strong>
        <p>This deck list only contained Basic Energy, which is intentionally ignored.</p>
      </div>`;
    return;
  }
  const missingItems = items.filter(item => item.missing > 0 || item.status === 'unresolved');
  const ownedByCard = new Map();
  items.forEach(item => item.fills.forEach(fill => {
    const existing = ownedByCard.get(fill.card_id);
    if (existing) {
      existing.quantity += fill.quantity;
      return;
    }
    ownedByCard.set(fill.card_id, {...fill});
  }));
  const ownedCards = [...ownedByCard.values()].sort((left, right) => left.name.localeCompare(right.name));

  const missingMarkup = missingItems.length
    ? missingItems.map(item => {
        const substitutes = item.possible_substitutes || [];
        return `
          <article class="deck-gallery-card deck-missing-card">
            <div class="deck-gallery-art ${item.image_url ? '' : 'image-missing'}">
              ${item.image_url ? `<img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.name)}" loading="lazy">` : ''}
              <span class="deck-gallery-badge">Need ${item.missing}</span>
            </div>
            <div class="deck-gallery-copy">
              <small>${escapeHtml(item.category)}</small>
              <h3>${escapeHtml(item.name)}</h3>
              <p>${escapeHtml(printingLabel(item))}</p>
              ${substitutes.length ? `
                <div class="deck-gallery-substitute">
                  <strong>Same-name substitute available</strong>
                  <span>${substitutes.map(card => `${card.quantity}× ${escapeHtml(printingLabel(card))}`).join(' · ')}</span>
                </div>` : ''}
            </div>
          </article>`;
      }).join('')
    : '<p class="deck-section-empty is-ready">No cards are missing.</p>';

  const ownedMarkup = ownedCards.length
    ? ownedCards.map(card => `
        <article class="deck-gallery-card deck-owned-card">
          <div class="deck-gallery-art ${card.image_url ? '' : 'image-missing'}">
            ${card.image_url ? `<img src="${escapeHtml(card.image_url)}" alt="${escapeHtml(card.name)}" loading="lazy">` : ''}
            <span class="deck-gallery-badge">×${card.quantity}</span>
          </div>
          <div class="deck-gallery-copy">
            <h3>${escapeHtml(card.name)}</h3>
            <p>${escapeHtml(printingLabel(card))}</p>
          </div>
        </article>`).join('')
    : '<p class="deck-section-empty">No owned cards were allocated to this deck.</p>';

  renderedDeckItems = [...items, ...ignoredBasicEnergy];
  const indexedItems = renderedDeckItems.map((item, index) => ({item, index}));
  const pokemonItems = indexedItems.filter(entry => deckGroup(entry.item) === 'pokemon');
  const trainerItems = indexedItems.filter(entry => deckGroup(entry.item) === 'trainer');
  const energyItems = indexedItems.filter(entry => deckGroup(entry.item) === 'energy');

  resultsContainer.innerHTML = `
    <section class="deck-result-section is-missing">
      <div class="deck-section-heading"><span>NEEDS ATTENTION</span><h2>Missing cards</h2></div>
      <div class="deck-card-gallery deck-missing-gallery">${missingMarkup}</div>
    </section>
    <section class="deck-result-section is-owned">
      <div class="deck-section-heading"><span>COVERED BY INVENTORY</span><h2>Cards you already have</h2></div>
      <div class="deck-card-gallery deck-owned-gallery">${ownedMarkup}</div>
    </section>
    <section class="deck-result-section is-full-deck">
      <div class="deck-section-heading"><span>COMPLETE IMPORT</span><h2>Full deck list</h2></div>
      <div class="deck-builder-layout">
        <div class="deck-builder-column">
          ${deckBuilderGroup('Pokémon', pokemonItems)}
          ${deckBuilderGroup('Energy', energyItems)}
        </div>
        <div class="deck-builder-column">
          ${deckBuilderGroup('Trainer', trainerItems)}
        </div>
        <aside id="deck_builder_preview" class="deck-builder-preview" aria-live="polite"></aside>
      </div>
    </section>`;

  document.querySelectorAll('.deck-builder-row').forEach(row => {
    row.addEventListener('click', () => selectDeckItem(Number(row.dataset.deckIndex)));
  });
  const firstMissing = renderedDeckItems.findIndex(item => item.missing > 0 || item.status === 'unresolved');
  selectDeckItem(firstMissing >= 0 ? firstMissing : 0);
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  submitButton.disabled = true;
  submitButton.textContent = 'Checking…';
  statusText.textContent = 'Comparing the deck with your local inventory…';
  summary.hidden = true;
  errorsContainer.hidden = true;
  resultsContainer.innerHTML = '';
  try {
    const response = await fetch('/deck/check', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({deck_list: deckList.value}),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'Deck check failed.');
    renderSummary(data);
    renderErrors(data.errors);
    renderResults(data.items, data.ignored_basic_energy || []);
    const ignored = data.summary.ignored_basic_energy_cards || 0;
    statusText.textContent = `${data.summary.unique_lines} deck entries checked. ${ignored ? `${ignored} Basic Energy ${ignored === 1 ? 'card was' : 'cards were'} ignored. ` : ''}Your collection was not changed.`;
  } catch (error) {
    statusText.textContent = error.message;
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = 'Check my inventory';
  }
});
