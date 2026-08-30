const SEARCH_ITERATION = 18;
const searchForm = document.querySelector('#catalog_search_form');
const queryInput = document.querySelector('#catalog_query');
const setFilter = document.querySelector('#catalog_set');
const formatFilter = document.querySelector('#catalog_format');
const cardTypeFilter = document.querySelector('#catalog_card_type');
const resultsContainer = document.querySelector('#catalog_results');
const statusText = document.querySelector('#catalog_status');
const previousButton = document.querySelector('#catalog_previous');
const nextButton = document.querySelector('#catalog_next');
const pageText = document.querySelector('#catalog_page');
const pagination = document.querySelector('#catalog_pagination');
const previousButtonBottom = document.querySelector('#catalog_previous_bottom');
const nextButtonBottom = document.querySelector('#catalog_next_bottom');
const pageTextBottom = document.querySelector('#catalog_page_bottom');
const paginationBottom = document.querySelector('#catalog_pagination_bottom');
const backToTopButton = document.querySelector('#catalog_back_to_top');
const activeFilters = document.querySelector('#catalog_active_filters');
const filterChips = document.querySelector('#catalog_filter_chips');
const resetFiltersButton = document.querySelector('#catalog_reset_filters');

const searchState = {offset: 0, limit: 48, total: 0, request: null, facetsLoaded: false, hasSearched: false};

function element(tag, className = '', text = '') {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function collectorLabel(card) {
  return card.printed_total ? `${card.number}/${card.printed_total}` : card.number;
}

function fillFacets(result) {
  if (searchState.facetsLoaded) return;
  result.sets.forEach(set => {
    const option = new Option(`${set.code} · ${set.name}`, set.id);
    setFilter.add(option);
  });
  searchState.facetsLoaded = true;
}

function hasCriteria() {
  return Boolean(queryInput.value.trim() || setFilter.value || formatFilter.value || cardTypeFilter.value);
}

function selectedOptionLabel(select) {
  return select.selectedOptions[0]?.textContent || '';
}

function filterChip(label, clear) {
  const chip = element('button', 'catalog-filter-chip');
  chip.type = 'button';
  chip.setAttribute('aria-label', `Remove ${label} filter`);
  chip.append(element('span', '', label), element('b', '', 'X'));
  chip.addEventListener('click', () => {
    clear();
    clearPendingResults();
  });
  return chip;
}

function renderActiveFilters() {
  const chips = [];
  const query = queryInput.value.trim();
  if (query) chips.push(filterChip(`Search: ${query}`, () => { queryInput.value = ''; queryInput.focus(); }));
  if (formatFilter.value) {
    const label = selectedOptionLabel(formatFilter).split(' ·')[0];
    chips.push(filterChip(`Format: ${label}`, () => { formatFilter.value = ''; }));
  }
  if (setFilter.value) chips.push(filterChip(`Set: ${selectedOptionLabel(setFilter)}`, () => { setFilter.value = ''; }));
  if (cardTypeFilter.value) chips.push(filterChip(`Type: ${selectedOptionLabel(cardTypeFilter)}`, () => { cardTypeFilter.value = ''; }));
  filterChips.replaceChildren(...chips);
  if (!chips.length) filterChips.append(element('em', '', 'No active filters'));
  resetFiltersButton.hidden = !(
    query || setFilter.value || cardTypeFilter.value || formatFilter.value !== 'standard'
  );
  activeFilters.classList.toggle('is-empty', !chips.length);
}

function renderWelcome() {
  const welcome = element('div', 'catalog-welcome');
  const icon = element('span', '', '⌕');
  icon.setAttribute('aria-hidden', 'true');
  welcome.append(icon);
  welcome.append(element('strong', '', 'Search when you are ready.'));
  welcome.append(element('p', '', 'Select a format, set, card type, or enter a name or number. Press Enter or use the Search button to see matching cards.'));
  resultsContainer.replaceChildren(welcome);
}

function clearPendingResults() {
  if (searchState.request) {
    searchState.request.abort();
    searchState.request = null;
  }
  searchState.hasSearched = false;
  searchState.total = 0;
  searchState.offset = 0;
  pagination.hidden = true;
  paginationBottom.hidden = true;
  renderWelcome();
  statusText.textContent = hasCriteria()
    ? 'Choices ready. Press Enter or Search cards to display results.'
    : 'Choose at least one search option, then press Enter or Search cards.';
  renderActiveFilters();
}

function setQuantityFeedback(feedback, message, state = '') {
  feedback.textContent = message;
  feedback.className = `catalog-save-feedback${state ? ` is-${state}` : ''}`;
}

async function commitQuantity(card, input, feedback, requested) {
  const quantity = Number(requested);
  if (!Number.isInteger(quantity) || quantity < 0 || quantity > 9999) {
    input.value = String(card.quantity);
    setQuantityFeedback(feedback, 'Enter a whole number from 0 to 9999.', 'error');
    return;
  }
  input.disabled = true;
  input.closest('.catalog-quantity-controls').classList.add('is-saving');
  setQuantityFeedback(feedback, 'Saving...', 'saving');
  try {
    const response = await fetch('/inventory/set-quantity', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({card_id: card.id, quantity}),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || 'Quantity update failed');
    card.quantity = result.inventory.quantity;
    input.value = String(card.quantity);
    input.dataset.savedValue = String(card.quantity);
    setQuantityFeedback(feedback, `Saved: ${card.quantity} owned`, 'saved');
  } catch (error) {
    input.value = String(card.quantity);
    setQuantityFeedback(feedback, `Could not save: ${error.message}`, 'error');
  } finally {
    input.disabled = false;
    input.closest('.catalog-quantity-controls').classList.remove('is-saving');
  }
}

function quantityControls(card) {
  const wrap = element('div', 'catalog-quantity');
  wrap.append(element('span', 'catalog-owned-label', 'CURRENT OWNED'));
  const controls = element('div', 'catalog-quantity-controls');
  const minus = element('button', 'catalog-quantity-button', '−');
  minus.type = 'button';
  minus.setAttribute('aria-label', `Remove one ${card.name}`);
  const input = document.createElement('input');
  input.type = 'number';
  input.inputMode = 'numeric';
  input.min = '0';
  input.max = '9999';
  input.step = '1';
  input.value = String(card.quantity);
  input.dataset.savedValue = String(card.quantity);
  input.setAttribute('aria-label', `${card.name} quantity owned`);
  const plus = element('button', 'catalog-quantity-button', '+');
  plus.type = 'button';
  plus.setAttribute('aria-label', `Add one ${card.name}`);
  const feedback = element('span', 'catalog-save-feedback');
  feedback.setAttribute('role', 'status');
  feedback.setAttribute('aria-live', 'polite');
  minus.addEventListener('pointerdown', event => event.preventDefault());
  plus.addEventListener('pointerdown', event => event.preventDefault());
  minus.addEventListener('click', () => commitQuantity(card, input, feedback, Math.max(0, Number(input.value) - 1)));
  plus.addEventListener('click', () => commitQuantity(card, input, feedback, Number(input.value) + 1));
  input.addEventListener('change', () => commitQuantity(card, input, feedback, input.value));
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter') {
      event.preventDefault();
      input.blur();
    }
  });
  controls.append(minus, input, plus);
  wrap.append(controls, feedback);
  return wrap;
}

function renderCards(cards) {
  resultsContainer.replaceChildren();
  if (!cards.length) {
    resultsContainer.append(element('p', 'catalog-empty', 'No local catalog cards match those search filters.'));
    return;
  }
  cards.forEach(card => {
    const row = element('article', 'catalog-result-row');
    const art = element('button', 'catalog-result-art');
    art.type = 'button';
    art.title = `Enlarge ${card.name}`;
    art.setAttribute('aria-label', `Enlarge ${card.name} card artwork`);
    const image = document.createElement('img');
    image.loading = 'lazy';
    image.decoding = 'async';
    image.alt = `${card.name} card`;
    if (card.image_url) image.src = card.image_url;
    image.addEventListener('error', () => art.classList.add('image-missing'), {once: true});
    art.append(image);
    art.addEventListener('click', () => window.CardInspector.open(card, art));
    const details = element('div', 'catalog-result-details');
    details.append(element('strong', '', card.name));
    details.append(element('span', '', `${card.set_code} · ${collectorLabel(card)}`));
    details.append(element('small', '', card.set_name));
    row.append(art, details, quantityControls(card));
    resultsContainer.append(row);
  });
}

function updatePagination() {
  const first = searchState.total ? searchState.offset + 1 : 0;
  const last = Math.min(searchState.offset + searchState.limit, searchState.total);
  const label = searchState.total ? `${first}–${last} of ${searchState.total}` : '0 results';
  const atStart = searchState.offset === 0;
  const atEnd = searchState.offset + searchState.limit >= searchState.total;
  for (const [container, previous, page, next] of [
    [pagination, previousButton, pageText, nextButton],
    [paginationBottom, previousButtonBottom, pageTextBottom, nextButtonBottom],
  ]) {
    page.textContent = label;
    previous.disabled = atStart;
    next.disabled = atEnd;
    container.hidden = false;
  }
}

async function loadCatalog() {
  if (searchState.request) searchState.request.abort();
  searchState.request = new AbortController();
  const parameters = new URLSearchParams({
    q: queryInput.value.trim(),
    set: setFilter.value,
    format: formatFilter.value,
    type: cardTypeFilter.value,
    limit: String(searchState.limit),
    offset: String(searchState.offset),
  });
  statusText.textContent = 'Searching the local catalog…';
  try {
    const response = await fetch(`/catalog/search?${parameters}`, {cache: 'no-store', signal: searchState.request.signal});
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || 'Catalog search failed');
    fillFacets(result);
    searchState.total = result.total;
    renderCards(result.items);
    updatePagination();
    statusText.textContent = result.total
      ? `${result.total.toLocaleString()} matching English card${result.total === 1 ? '' : 's'}. Quantities save immediately.`
      : 'No cards matched. Try fewer words or clear a filter.';
  } catch (error) {
    if (error.name === 'AbortError') return;
    resultsContainer.replaceChildren();
    pagination.hidden = true;
    paginationBottom.hidden = true;
    statusText.textContent = error.message;
  }
}

function restartSearch() {
  if (!hasCriteria()) {
    clearPendingResults();
    statusText.textContent = 'Choose at least one search option before searching.';
    queryInput.focus();
    return;
  }
  searchState.offset = 0;
  searchState.hasSearched = true;
  void loadCatalog();
}

searchForm.addEventListener('submit', event => { event.preventDefault(); restartSearch(); });
[queryInput, setFilter, formatFilter, cardTypeFilter].forEach(control => {
  control.addEventListener(control === queryInput ? 'input' : 'change', clearPendingResults);
  control.addEventListener('keydown', event => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    restartSearch();
  });
});
function previousPage() {
  searchState.offset = Math.max(0, searchState.offset - searchState.limit);
  void loadCatalog();
  window.scrollTo({top: 0, behavior: 'smooth'});
}

function nextPage() {
  searchState.offset += searchState.limit;
  void loadCatalog();
  window.scrollTo({top: 0, behavior: 'smooth'});
}

previousButton.addEventListener('click', previousPage);
previousButtonBottom.addEventListener('click', previousPage);
nextButton.addEventListener('click', nextPage);
nextButtonBottom.addEventListener('click', nextPage);
backToTopButton.addEventListener('click', () => {
  window.scrollTo({top: 0, behavior: 'smooth'});
});
resetFiltersButton.addEventListener('click', () => {
  queryInput.value = '';
  formatFilter.value = 'standard';
  setFilter.value = '';
  cardTypeFilter.value = '';
  clearPendingResults();
});

async function startSearch() {
  try {
    const response = await fetch('/health', {cache: 'no-store'});
    const health = await response.json();
    if (!response.ok || health.iteration !== SEARCH_ITERATION || !health.local_catalog_available) {
      throw new Error(`Restart the collection app to load Iteration ${SEARCH_ITERATION} and its local catalog.`);
    }
    const facetsResponse = await fetch('/catalog/facets', {cache: 'no-store'});
    const facets = await facetsResponse.json();
    if (!facetsResponse.ok || !facets.ok) throw new Error(facets.error || 'Search options could not be loaded.');
    fillFacets(facets);
    clearPendingResults();
  } catch (error) {
    statusText.textContent = error.message;
  }
}

void startSearch();
