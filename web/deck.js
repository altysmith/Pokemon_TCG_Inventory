const form = document.querySelector('#deck_form');
const deckList = document.querySelector('#deck_list');
const submitButton = document.querySelector('#deck_submit');
const summary = document.querySelector('#deck_summary');
const statusText = document.querySelector('#deck_status');
const errorsContainer = document.querySelector('#deck_errors');
const resultsContainer = document.querySelector('#deck_results');
const libraryCards = document.querySelector('#deck_library_cards');
const libraryCount = document.querySelector('#deck_library_count');
const libraryStatus = document.querySelector('#deck_library_status');
const savePanel = document.querySelector('#deck_save_panel');
const deckName = document.querySelector('#deck_name');
const saveButton = document.querySelector('#deck_save');
const saveStatus = document.querySelector('#deck_save_status');
const newDeckButton = document.querySelector('#deck_new');

let savedDecks = [];
let renamingDeckId = 0;
let currentSavedDeckId = 0;
let lastCheckedDeckList = '';
let lastCheckedClipboardDeckList = '';

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

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || 'The request could not be completed.');
  return data;
}

async function copyTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const field = document.createElement('textarea');
  field.value = text;
  field.setAttribute('readonly', '');
  field.style.position = 'fixed';
  field.style.opacity = '0';
  document.body.append(field);
  field.select();
  const copied = document.execCommand('copy');
  field.remove();
  if (!copied) throw new Error('The deck list could not be copied.');
}

async function copyCheckedDeckList(button) {
  if (!lastCheckedClipboardDeckList) return;
  const originalLabel = button.textContent;
  button.disabled = true;
  try {
    await copyTextToClipboard(lastCheckedClipboardDeckList);
    button.textContent = 'Copied!';
    statusText.textContent = 'The full deck list was copied in import format.';
  } catch (error) {
    button.textContent = 'Copy failed';
    statusText.textContent = error.message;
  } finally {
    window.setTimeout(() => {
      button.textContent = originalLabel;
      button.disabled = false;
    }, 1600);
  }
}

function savedDeckDate(value) {
  const parsed = new Date(`${String(value).replace(' ', 'T')}Z`);
  if (Number.isNaN(parsed.getTime())) return value || '';
  return new Intl.DateTimeFormat(undefined, {month: 'short', day: 'numeric', year: 'numeric'}).format(parsed);
}

function setLibraryStatus(message, state = '') {
  libraryStatus.textContent = message;
  libraryStatus.className = `deck-library-status ${state ? `is-${state}` : ''}`;
}

function renderDeckLibrary() {
  libraryCount.textContent = `${savedDecks.length} ${savedDecks.length === 1 ? 'deck' : 'decks'}`;
  if (!savedDecks.length) {
    libraryCards.innerHTML = `
      <div class="deck-library-empty">
        <strong>No saved decks yet.</strong>
        <span>Check a deck below, give it a name, and save it here.</span>
      </div>`;
    return;
  }
  libraryCards.innerHTML = savedDecks.map(deck => {
    if (deck.id === renamingDeckId) {
      return `
        <article class="deck-library-card is-renaming">
          <form class="deck-library-rename" data-deck-id="${deck.id}">
            <label for="rename_deck_${deck.id}">New deck name</label>
            <input id="rename_deck_${deck.id}" name="name" maxlength="80" value="${escapeHtml(deck.name)}" required>
            <div><button type="submit">Save name</button><button class="is-secondary" type="button" data-cancel-rename>Cancel</button></div>
          </form>
        </article>`;
    }
    return `
      <article class="deck-library-card ${deck.id === currentSavedDeckId ? 'is-current' : ''}">
        <button class="deck-library-open" type="button" data-open-deck="${deck.id}">
          <small>SAVED DECK</small>
          <strong>${escapeHtml(deck.name)}</strong>
          <span>${deck.card_count} cards · ${deck.unique_entries} unique entries</span>
          <em>Open, check, and edit · Updated ${escapeHtml(savedDeckDate(deck.updated_at))}</em>
        </button>
        <div class="deck-library-card-actions">
          <button type="button" data-rename-deck="${deck.id}">Rename</button>
          <button class="is-remove" type="button" data-remove-deck="${deck.id}">Remove</button>
        </div>
      </article>`;
  }).join('');

  document.querySelectorAll('[data-open-deck]').forEach(button => {
    button.addEventListener('click', () => openSavedDeck(Number(button.dataset.openDeck)));
  });
  document.querySelectorAll('[data-rename-deck]').forEach(button => {
    button.addEventListener('click', () => {
      renamingDeckId = Number(button.dataset.renameDeck);
      renderDeckLibrary();
      document.querySelector(`#rename_deck_${renamingDeckId}`)?.focus();
    });
  });
  document.querySelectorAll('[data-remove-deck]').forEach(button => {
    button.addEventListener('click', () => removeSavedDeck(Number(button.dataset.removeDeck)));
  });
  document.querySelectorAll('[data-cancel-rename]').forEach(button => {
    button.addEventListener('click', () => {
      renamingDeckId = 0;
      renderDeckLibrary();
    });
  });
  document.querySelectorAll('.deck-library-rename').forEach(renameForm => {
    renameForm.addEventListener('submit', event => renameSavedDeck(event, renameForm));
  });
}

async function loadSavedDecks(message = '') {
  try {
    const data = await requestJson('/decks');
    savedDecks = data.decks;
    renderDeckLibrary();
    setLibraryStatus(message || (savedDecks.length ? 'Select a deck to open and recheck it.' : 'Your library is ready for its first deck.'), message ? 'saved' : '');
  } catch (error) {
    setLibraryStatus(error.message, 'error');
  }
}

async function renameSavedDeck(event, renameForm) {
  event.preventDefault();
  const id = Number(renameForm.dataset.deckId);
  const name = new FormData(renameForm).get('name');
  try {
    const data = await requestJson('/decks/rename', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({id, name}),
    });
    if (currentSavedDeckId === id) deckName.value = data.deck.name;
    renamingDeckId = 0;
    await loadSavedDecks(`Renamed to ${data.deck.name}.`);
  } catch (error) {
    setLibraryStatus(error.message, 'error');
  }
}

async function removeSavedDeck(id) {
  const deck = savedDecks.find(item => item.id === id);
  if (!deck || !window.confirm(`Remove ${deck.name} from your saved deck library?`)) return;
  try {
    await requestJson('/decks/remove', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({id}),
    });
    if (currentSavedDeckId === id) {
      currentSavedDeckId = 0;
      savePanel.hidden = true;
    }
    await loadSavedDecks(`${deck.name} was removed from the library.`);
  } catch (error) {
    setLibraryStatus(error.message, 'error');
  }
}

function configureSavePanel(data) {
  if (data.errors.length) {
    savePanel.hidden = true;
    return;
  }
  savePanel.hidden = false;
  const saved = savedDecks.find(deck => deck.id === currentSavedDeckId);
  if (saved) {
    deckName.value = saved.name;
    deckName.disabled = true;
    const changed = lastCheckedDeckList !== saved.deck_list.trim();
    saveButton.disabled = !changed;
    saveButton.textContent = changed ? 'Update saved deck' : 'Saved in library';
    saveStatus.textContent = changed
      ? 'This will replace the saved list and refresh its owned-card assignments.'
      : 'This saved list was rechecked against your current inventory. Edit it and check again to update it.';
    return;
  }
  deckName.disabled = false;
  saveButton.disabled = false;
  saveButton.textContent = 'Save to deck library';
  saveStatus.textContent = 'Saving automatically labels available owned copies without changing quantities or storage locations.';
}

async function saveCheckedDeck() {
  if (!lastCheckedDeckList || deckList.value.trim() !== lastCheckedDeckList) {
    saveStatus.textContent = 'Check this deck again before saving it.';
    return false;
  }
  saveButton.disabled = true;
  saveButton.textContent = 'Saving…';
  try {
    const data = await requestJson('/decks/save', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        id: currentSavedDeckId || 0,
        name: deckName.value,
        deck_list: lastCheckedDeckList,
      }),
    });
    currentSavedDeckId = data.deck.id;
    await loadSavedDecks(`${data.deck.name} was saved and its owned-card assignments were refreshed.`);
    configureSavePanel({errors: []});
    saveStatus.textContent = 'The saved list and its owned-card assignments now match. Inventory quantities and storage locations were unchanged.';
    return true;
  } catch (error) {
    saveButton.disabled = false;
    saveButton.textContent = currentSavedDeckId ? 'Update saved deck' : 'Save to deck library';
    saveStatus.textContent = error.message;
    return false;
  }
}

function startNewDeck() {
  currentSavedDeckId = 0;
  lastCheckedDeckList = '';
  lastCheckedClipboardDeckList = '';
  deckList.value = '';
  deckName.value = '';
  deckName.disabled = false;
  savePanel.hidden = true;
  summary.hidden = true;
  errorsContainer.hidden = true;
  resultsContainer.replaceChildren();
  statusText.textContent = 'Paste a new deck list when you are ready.';
  renderDeckLibrary();
  deckList.focus();
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

function collectorNumberKey(value) {
  const normalized = String(value || '').trim().toLowerCase();
  return normalized.replace(/^0+(?=\d)/, '');
}

function replaceDeckPrinting(item, substitute) {
  let remaining = Number(substitute.quantity || 0);
  const sourceName = String(item.name || '').trim().toLowerCase();
  const sourceSet = String(item.set_code || '').trim().toLowerCase();
  const sourceNumber = collectorNumberKey(item.number);
  const updatedLines = deckList.value.split(/\r?\n/).flatMap(line => {
    if (remaining <= 0) return [line];
    const match = line.match(/^(\s*)(\d+)\s+(.+?)\s+(\S+)\s+(\S+)(\s*)$/);
    if (!match) return [line];
    const [, indentation, quantityText, name, setCode, number, trailing] = match;
    if (
      name.trim().toLowerCase() !== sourceName
      || setCode.toLowerCase() !== sourceSet
      || collectorNumberKey(number) !== sourceNumber
    ) return [line];
    const quantity = Number(quantityText);
    const take = Math.min(quantity, remaining);
    remaining -= take;
    const replacement = `${indentation}${take} ${substitute.name} ${substitute.set_code} ${substitute.number}${trailing}`;
    if (take === quantity) return [replacement];
    return [
      replacement,
      `${indentation}${quantity - take} ${name} ${setCode} ${number}${trailing}`,
    ];
  });
  if (remaining > 0) throw new Error('The original deck entry could not be updated.');
  return updatedLines.join('\n');
}

async function useSameNameSubstitute(itemIndex, substituteIndex, button) {
  const item = renderedDeckItems[itemIndex];
  const substitute = item?.possible_substitutes?.[substituteIndex];
  if (!item || !substitute) return;
  const savedDeckId = currentSavedDeckId;
  button.disabled = true;
  statusText.textContent = `Swapping ${substitute.quantity} ${item.name} to ${printingLabel(substitute)}…`;
  try {
    const updatedDeckList = replaceDeckPrinting(item, substitute);
    deckList.value = updatedDeckList;
    await checkCurrentDeck();
    if (lastCheckedDeckList !== updatedDeckList.trim()) {
      throw new Error('The updated deck could not be rechecked.');
    }
    if (savedDeckId && !savePanel.hidden) {
      const saved = await saveCheckedDeck();
      if (!saved) throw new Error(saveStatus.textContent || 'The updated deck could not be saved.');
      statusText.textContent = `${substitute.quantity}× ${item.name} was changed to ${printingLabel(substitute)} and saved to the deck.`;
    } else {
      statusText.textContent = `${substitute.quantity}× ${item.name} was changed to ${printingLabel(substitute)}. Save the deck when you are ready.`;
    }
  } catch (error) {
    button.disabled = false;
    statusText.textContent = error.message;
  }
}

function deckBuilderRow(item, index) {
  const statusClass = item.status === 'ready' ? 'is-ready' : item.status === 'ignored' ? 'is-ignored' : 'is-needed';
  return `
    <button class="deck-builder-row ${statusClass}" type="button" data-deck-index="${index}" aria-label="Show ${escapeHtml(item.name)}, ${item.requested} in deck, ${escapeHtml(deckItemState(item))}">
      <strong>${item.requested}</strong>
      <span><em>${escapeHtml(item.name)}</em>${item.set_code ? `<small>${escapeHtml(item.set_code)}</small>` : ''}</span>
      <b>${escapeHtml(deckItemState(item))}</b>
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

function renderDeckBuilderPreview(item) {
  const preview = document.querySelector('#deck_builder_preview');
  if (!preview || !item) return;
  preview.innerHTML = `
    <div class="deck-builder-preview-heading">
      <small>Selected card</small>
      <h3>${escapeHtml(item.name)}</h3>
    </div>
    <div class="deck-builder-preview-art ${item.image_url ? '' : 'image-missing'}">
      ${item.image_url ? `<img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.name)} card">` : ''}
    </div>
    <dl>
      <div><dt>Deck quantity</dt><dd>${item.requested}</dd></div>
      <div><dt>Printing</dt><dd>${escapeHtml(printingLabel(item))}</dd></div>
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
  renderedDeckItems = [...items, ...ignoredBasicEnergy];
  const missingItems = items.filter(item => item.missing > 0 || item.status === 'unresolved');

  const missingMarkup = missingItems.length
    ? missingItems.map(item => {
        const substitutes = item.possible_substitutes || [];
        const itemIndex = renderedDeckItems.indexOf(item);
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
                  ${substitutes.map((card, substituteIndex) => `
                    <button type="button" data-substitute-item="${itemIndex}" data-substitute-index="${substituteIndex}">
                      Use ${card.quantity}× ${escapeHtml(printingLabel(card))}
                    </button>`).join('')}
                </div>` : ''}
              <a class="deck-tcgplayer-link" href="${escapeHtml(tcgplayerSearchUrl(item))}" target="_blank" rel="noopener noreferrer" aria-label="Find ${escapeHtml(item.name)} on TCGplayer">
                Find on TCGplayer <span aria-hidden="true">↗</span>
              </a>
            </div>
          </article>`;
      }).join('')
    : '<p class="deck-section-empty is-ready">No cards are missing.</p>';

  const indexedItems = renderedDeckItems.map((item, index) => ({item, index}));
  const pokemonItems = indexedItems.filter(entry => deckGroup(entry.item) === 'pokemon');
  const trainerItems = indexedItems.filter(entry => deckGroup(entry.item) === 'trainer');
  const energyItems = indexedItems.filter(entry => deckGroup(entry.item) === 'energy');

  resultsContainer.innerHTML = `
    <section class="deck-result-section is-missing">
      <div class="deck-section-heading"><span>NEEDS ATTENTION</span><h2>Missing cards</h2></div>
      <div class="deck-card-gallery deck-missing-gallery">${missingMarkup}</div>
    </section>
    <section class="deck-result-section is-full-deck">
      <div class="deck-section-heading has-actions">
        <div><span>LIMITLESS-STYLE VIEW</span><h2>Full deck list</h2></div>
        <button id="deck_copy_full_list" type="button">Copy deck list</button>
      </div>
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

  const builderRows = [...document.querySelectorAll('.deck-builder-row')];
  builderRows.forEach(row => {
    row.addEventListener('click', () => {
      builderRows.forEach(candidate => candidate.classList.toggle('is-selected', candidate === row));
      renderDeckBuilderPreview(renderedDeckItems[Number(row.dataset.deckIndex)]);
    });
  });
  if (builderRows.length) {
    builderRows[0].classList.add('is-selected');
    renderDeckBuilderPreview(renderedDeckItems[Number(builderRows[0].dataset.deckIndex)]);
  }
  document.querySelectorAll('[data-substitute-item]').forEach(button => {
    button.addEventListener('click', () => void useSameNameSubstitute(
      Number(button.dataset.substituteItem),
      Number(button.dataset.substituteIndex),
      button,
    ));
  });
  document.querySelector('#deck_copy_full_list')?.addEventListener('click', (event) => void copyCheckedDeckList(event.currentTarget));
}

async function checkCurrentDeck() {
  submitButton.disabled = true;
  submitButton.textContent = 'Checking…';
  statusText.textContent = 'Comparing the deck with your local inventory…';
  summary.hidden = true;
  savePanel.hidden = true;
  errorsContainer.hidden = true;
  resultsContainer.innerHTML = '';
  try {
    const checkedDeckList = deckList.value.trim();
    const data = await requestJson('/deck/check', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({deck_list: checkedDeckList}),
    });
    lastCheckedDeckList = checkedDeckList;
    lastCheckedClipboardDeckList = data.clipboard_deck_list || checkedDeckList;
    renderSummary(data);
    renderErrors(data.errors);
    renderResults(data.items, data.ignored_basic_energy || []);
    configureSavePanel(data);
    const ignored = data.summary.ignored_basic_energy_cards || 0;
    statusText.textContent = `${data.summary.unique_lines} deck entries checked. ${ignored ? `${ignored} Basic Energy ${ignored === 1 ? 'card was' : 'cards were'} ignored. ` : ''}Your collection was not changed.`;
  } catch (error) {
    lastCheckedDeckList = '';
    lastCheckedClipboardDeckList = '';
    statusText.textContent = error.message;
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = 'Check my inventory';
  }
}

async function openSavedDeck(id) {
  const deck = savedDecks.find(item => item.id === id);
  if (!deck) return;
  currentSavedDeckId = id;
  deckList.value = deck.deck_list;
  deckName.value = deck.name;
  renderDeckLibrary();
  form.scrollIntoView({behavior: 'smooth', block: 'start'});
  await checkCurrentDeck();
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  await checkCurrentDeck();
});

deckList.addEventListener('input', () => {
  if (deckList.value.trim() === lastCheckedDeckList) return;
  savePanel.hidden = true;
  statusText.textContent = currentSavedDeckId
    ? 'Deck list changed. Check it again before updating the saved deck.'
    : 'Deck list changed. Check it before saving.';
});

saveButton.addEventListener('click', saveCheckedDeck);
newDeckButton.addEventListener('click', startNewDeck);
deckName.addEventListener('keydown', event => {
  if (event.key === 'Enter') {
    event.preventDefault();
    saveCheckedDeck();
  }
});

async function startDeckPage() {
  await loadSavedDecks();
  const requestedDeck = Number(new URLSearchParams(window.location.search).get('deck'));
  if (requestedDeck > 0 && savedDecks.some((deck) => deck.id === requestedDeck)) {
    await openSavedDeck(requestedDeck);
  }
}

void startDeckPage();
