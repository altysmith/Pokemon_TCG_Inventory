const groupsContainer = document.querySelector('#inventory_groups');
const statusText = document.querySelector('#inventory_status');
const searchInput = document.querySelector('#inventory_search');
const sortSelect = document.querySelector('#inventory_sort');
const setFilter = document.querySelector('#set_filter');
const exportCsv = document.querySelector('#inventory_export_csv');
const exportJson = document.querySelector('#inventory_export_json');
const modeButtons = [...document.querySelectorAll('[data-mode]')];
const categoryNavigation = document.querySelector('#category_navigation');
const allButton = document.querySelector('[data-category="all"]');
const locationNavigation = document.querySelector('#location_navigation');
const locationManage = document.querySelector('#location_manage');
const recentButton = document.querySelector('#recent_button');
const alphabetNavigation = document.querySelector('#alphabet_navigation');
const viewEyebrow = document.querySelector('#view_eyebrow');
const viewTitle = document.querySelector('#view_title');
const viewCount = document.querySelector('#view_count');
const drawer = document.querySelector('#card_drawer');
const drawerClose = document.querySelector('#drawer_close');
const drawerQuantitySummary = document.querySelector('#drawer_quantity_summary');
const drawerQuantityInput = document.querySelector('#drawer_quantity_input');
const drawerQuantityDecrease = document.querySelector('#drawer_quantity_decrease');
const drawerQuantityIncrease = document.querySelector('#drawer_quantity_increase');
const drawerQuantitySave = document.querySelector('#drawer_quantity_save');
const drawerQuantityFeedback = document.querySelector('#drawer_quantity_feedback');
const drawerLocationSelect = document.querySelector('#drawer_location_select');
const drawerLocationQuantity = document.querySelector('#drawer_location_quantity');
const drawerLocationSave = document.querySelector('#drawer_location_save');
const drawerLocationManage = document.querySelector('#drawer_location_manage');
const drawerLocationFeedback = document.querySelector('#drawer_location_feedback');
const drawerLocationAllocations = document.querySelector('#drawer_location_allocations');
const drawerUnassignedSummary = document.querySelector('#drawer_unassigned_summary');
const importOpen = document.querySelector('#inventory_import_open');
const importDialog = document.querySelector('#inventory_import_dialog');
const importClose = document.querySelector('#inventory_import_close');
const importFile = document.querySelector('#inventory_import_file');
const importPreviewButton = document.querySelector('#inventory_import_preview');
const importStatus = document.querySelector('#inventory_import_status');
const importResults = document.querySelector('#inventory_import_results');
const importErrors = document.querySelector('#inventory_import_errors');
const importChangeFilter = document.querySelector('#inventory_import_change_filter');
const importSearch = document.querySelector('#inventory_import_search');
const importChanges = document.querySelector('#inventory_import_changes');
const importPrevious = document.querySelector('#inventory_import_previous');
const importNext = document.querySelector('#inventory_import_next');
const importPage = document.querySelector('#inventory_import_page');
const importApply = document.querySelector('#inventory_import_apply');
const locationsDialog = document.querySelector('#inventory_locations_dialog');
const locationsClose = document.querySelector('#inventory_locations_close');
const locationCreateForm = document.querySelector('#inventory_location_create');
const locationNameInput = document.querySelector('#inventory_location_name');
const locationsStatus = document.querySelector('#inventory_locations_status');
const locationsList = document.querySelector('#inventory_locations_list');
const collectionDecks = document.querySelector('#collection_decks');
const collectionDecksStatus = document.querySelector('#collection_decks_status');
const deckEditorDialog = document.querySelector('#deck_editor_dialog');
const deckEditorClose = document.querySelector('#deck_editor_close');
const deckEditorTitle = document.querySelector('#deck_editor_title');
const deckEditorSummary = document.querySelector('#deck_editor_summary');
const deckEditorStatus = document.querySelector('#deck_editor_status');
const deckEditorTotal = document.querySelector('#deck_editor_total');
const deckEditorEntries = document.querySelector('#deck_editor_entries');
const deckEditorFullCheck = document.querySelector('#deck_editor_full_check');
const deckEditorAssign = document.querySelector('#deck_editor_assign');
const deckEditorSearchForm = document.querySelector('#deck_editor_search_form');
const deckEditorQuery = document.querySelector('#deck_editor_query');
const deckEditorType = document.querySelector('#deck_editor_type');
const deckEditorSearchResults = document.querySelector('#deck_editor_search_results');
const selectionStart = document.querySelector('#collection_selection_start');
const selectionActions = document.querySelector('#collection_selection_actions');
const selectionCount = document.querySelector('#collection_selection_count');
const selectionAll = document.querySelector('#collection_selection_all');
const selectionClear = document.querySelector('#collection_selection_clear');
const selectionMove = document.querySelector('#collection_selection_move');
const selectionCancel = document.querySelector('#collection_selection_cancel');
const moveDialog = document.querySelector('#inventory_move_dialog');
const moveForm = document.querySelector('#inventory_move_form');
const moveClose = document.querySelector('#inventory_move_close');
const moveSummary = document.querySelector('#inventory_move_summary');
const moveSource = document.querySelector('#inventory_move_source');
const moveDestination = document.querySelector('#inventory_move_destination');
const moveDeckOption = document.querySelector('#inventory_move_deck_option');
const moveStatus = document.querySelector('#inventory_move_status');
const moveManage = document.querySelector('#inventory_move_manage');

const CARD_IMAGE_MAX_CONCURRENT = 6;
const CARD_IMAGE_MAX_RETRIES = 2;
const CARD_IMAGE_PRIORITY_COUNT = 18;
const CARD_IMAGE_TIMEOUT_MS = 7000;
const cardImageQueue = [];
let activeCardImageLoads = 0;
let cardImageObserver = null;
let cardImageGeneration = 0;
const IMPORT_PREVIEW_PAGE_SIZE = 75;
const importState = {
  content: '',
  filename: '',
  preview: null,
  page: 1,
};

const CATEGORY_GROUPS = [
  {
    mount: '#pokemon_categories',
    label: 'Pokémon',
    items: [
      ['grass', 'Grass', '◒'], ['fire', 'Fire', '◆'], ['water', 'Water', '●'],
      ['lightning', 'Lightning', 'ϟ'], ['psychic', 'Psychic', '◉'],
      ['fighting', 'Fighting', '✦'], ['darkness', 'Darkness', '◐'],
      ['metal', 'Metal', '⬡'], ['dragon', 'Dragon', '⌁'],
      ['colorless', 'Colorless', '○'],
    ],
  },
  {
    mount: '#trainer_categories',
    label: 'Trainers',
    items: [
      ['item', 'Items', '▣'], ['tool', 'Pokémon Tools', '⌕'],
      ['supporter', 'Supporters', '♙'], ['stadium', 'Stadiums', '▤'],
    ],
  },
  {
    mount: '#energy_categories',
    label: 'Energy',
    items: [
      ['basic-energy', 'Basic Energy', '◈'], ['special-energy', 'Special Energy', '◇'],
    ],
  },
  {
    mount: '#special_categories',
    label: 'Special',
    items: [['ace-spec', 'ACE SPEC', '✦']],
  },
];

const CATEGORY_LABELS = new Map(
  CATEGORY_GROUPS.flatMap((group) => group.items.map(([key, label]) => [key, label])),
);
const CATEGORY_ORDER = new Map(
  CATEGORY_GROUPS.flatMap((group) => group.items).map(([key], index) => [key, index]),
);

const state = {
  items: [],
  locations: [],
  unassigned: {unique_cards: 0, total_copies: 0},
  location: 'all',
  mode: 'typing',
  category: 'all',
  recent: false,
  query: '',
  set: 'all',
  sort: 'name_az',
  selectedId: null,
};
const selectionState = {
  active: false,
  quantities: new Map(),
  deckName: '',
};
let savedDecks = [];
const deckEditorState = {deckId: 0, entries: [], searching: false};

function titleCase(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/(^|[ _-])([a-z])/g, (_match, space, letter) => `${space === '_' ? ' ' : space}${letter.toUpperCase()}`);
}

function isAceSpec(card) {
  return card.is_ace_spec === true || String(card.rarity || '').toUpperCase() === 'ACE_SPEC_RARE';
}

function categoryKey(card) {
  if (card.card_type === 'POKEMON') return String(card.types?.[0] || 'colorless').toLowerCase();
  if (card.card_type === 'TRAINER') {
    const subtype = String(card.card_subtype || card.display_subtype || '').toLowerCase();
    if (subtype.includes('tool')) return 'tool';
    if (subtype.includes('supporter')) return 'supporter';
    if (subtype.includes('stadium')) return 'stadium';
    return 'item';
  }
  if (card.card_type === 'ENERGY') {
    return String(card.card_subtype || '').toLowerCase().includes('special') ? 'special-energy' : 'basic-energy';
  }
  return 'other';
}

function categoryLabel(card) {
  const key = categoryKey(card);
  return CATEGORY_LABELS.get(key) || card.display_subtype || titleCase(card.card_type);
}

function categoryMatches(card, key) {
  return key === 'ace-spec' ? isAceSpec(card) : categoryKey(card) === key;
}

function cardLocationQuantity(card, location = state.location) {
  if (location === 'all') return card.quantity;
  if (location === 'unassigned') return card.unassigned_quantity || 0;
  return Number(card.locations?.[String(location)] || 0);
}

function locationFilteredCards() {
  return state.items.filter((card) => cardLocationQuantity(card) > 0);
}

function selectedLocation() {
  return state.locations.find((location) => String(location.id) === String(state.location)) || null;
}

function recalculateLocationCounts() {
  for (const location of state.locations) {
    const quantities = state.items.map((card) => Number(card.locations?.[String(location.id)] || 0));
    location.unique_cards = quantities.filter((quantity) => quantity > 0).length;
    location.total_copies = quantities.reduce((sum, quantity) => sum + quantity, 0);
  }
  const unassigned = state.items.map((card) => Number(card.unassigned_quantity || 0));
  state.unassigned = {
    unique_cards: unassigned.filter((quantity) => quantity > 0).length,
    total_copies: unassigned.reduce((sum, quantity) => sum + quantity, 0),
  };
}

async function inventoryRequest(url, payload) {
  const response = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || 'The inventory request could not be completed.');
  return data;
}

const COLLECTION_EXPORT_FIELDS = [
  'schema', 'schema_version', 'card_id', 'quantity', 'name', 'set_name', 'set_code',
  'number', 'printed_total', 'card_type', 'card_subtype', 'types', 'regulation_mark',
  'rarity', 'date_added', 'date_updated',
];

function collectionExportPayload(items, exportedAt = new Date().toISOString()) {
  const cards = items.map((item) => ({
    card_id: item.id,
    quantity: Number(item.quantity),
    name: item.name || '',
    set_name: item.set_name || '',
    set_code: item.set_code || '',
    number: item.number || '',
    printed_total: item.printed_total || '',
    card_type: item.card_type || '',
    card_subtype: item.card_subtype || '',
    types: [...(item.types || [])],
    regulation_mark: item.regulation_mark || '',
    rarity: item.rarity || '',
    date_added: item.date_added || '',
    date_updated: item.date_updated || '',
  }));
  return {
    schema: 'pokemon-card-collection',
    schema_version: 1,
    exported_at: exportedAt,
    application: 'Pokemon Card Collection',
    summary: {
      unique_cards: cards.length,
      total_copies: cards.reduce((sum, card) => sum + card.quantity, 0),
    },
    cards,
  };
}

function csvValue(value) {
  const text = String(value ?? '');
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function collectionExportCsv(payload) {
  const rows = payload.cards.map((card) => ({
    schema: payload.schema,
    schema_version: payload.schema_version,
    ...card,
    types: card.types.join('|'),
  }));
  return [
    COLLECTION_EXPORT_FIELDS.join(','),
    ...rows.map((row) => COLLECTION_EXPORT_FIELDS.map((field) => csvValue(row[field])).join(',')),
  ].join('\r\n') + '\r\n';
}

function exportFilename(extension) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  }).formatToParts(new Date());
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `pokemon-collection-${value.year}${value.month}${value.day}-${value.hour}${value.minute}${value.second}.${extension}`;
}

function prepareCollectionExport(event, format) {
  const payload = collectionExportPayload(state.items);
  const content = format === 'json'
    ? `${JSON.stringify(payload, null, 2)}\n`
    : `\ufeff${collectionExportCsv(payload)}`;
  const type = format === 'json' ? 'application/json;charset=utf-8' : 'text/csv;charset=utf-8';
  const url = URL.createObjectURL(new Blob([content], {type}));
  event.currentTarget.href = url;
  event.currentTarget.download = exportFilename(format);
  statusText.textContent = `${format.toUpperCase()} export downloaded: ${payload.summary.unique_cards} unique cards, ${payload.summary.total_copies} total copies.`;
  statusText.hidden = false;
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}

function collectorNumber(card) {
  return `${card.number}${card.printed_total ? `/${card.printed_total}` : ''}`;
}

function inventoryDate(value) {
  if (!value) return null;
  const date = new Date(`${String(value).replace(' ', 'T')}Z`);
  return Number.isNaN(date.valueOf()) ? null : date;
}

function renderCategoryNavigation() {
  const counts = new Map();
  for (const card of locationFilteredCards()) {
    const key = categoryKey(card);
    counts.set(key, (counts.get(key) || 0) + 1);
    if (isAceSpec(card)) counts.set('ace-spec', (counts.get('ace-spec') || 0) + 1);
  }
  document.querySelector('#count_all').textContent = String(state.items.length);
  for (const group of CATEGORY_GROUPS) {
    const mount = document.querySelector(group.mount);
    const fragment = document.createDocumentFragment();
    for (const [key, label, icon] of group.items) {
      const button = document.createElement('button');
      button.className = 'binder-nav-item';
      button.type = 'button';
      button.dataset.category = key;
      button.dataset.tone = key;
      button.innerHTML = `<span class="binder-nav-icon" aria-hidden="true">${icon}</span><span></span><b></b>`;
      button.children[1].textContent = label;
      button.children[2].textContent = String(counts.get(key) || 0);
      fragment.append(button);
    }
    mount.replaceChildren(fragment);
  }
}

function renderLocationNavigation() {
  document.querySelector('#count_unassigned').textContent = String(state.unassigned.unique_cards || 0);
  const fragment = document.createDocumentFragment();
  for (const location of state.locations) {
    const button = document.createElement('button');
    button.className = 'binder-nav-item';
    button.type = 'button';
    button.dataset.location = String(location.id);
    button.innerHTML = '<span class="binder-nav-icon" aria-hidden="true">□</span><span></span><b></b>';
    button.children[1].textContent = location.name;
    button.children[2].textContent = String(location.unique_cards);
    fragment.append(button);
  }
  locationNavigation.replaceChildren(fragment);
}

function renderSetOptions() {
  const sets = [...new Map(state.items.map((card) => [card.set_code, card.set_name])).entries()]
    .sort((left, right) => left[1].localeCompare(right[1]));
  const fragment = document.createDocumentFragment();
  const all = document.createElement('option');
  all.value = 'all';
  all.textContent = 'All owned sets';
  fragment.append(all);
  for (const [code, name] of sets) {
    const option = document.createElement('option');
    option.value = code;
    option.textContent = `${name} (${code})`;
    fragment.append(option);
  }
  setFilter.replaceChildren(fragment);
}

function setSortOptions() {
  const options = [
    ['name_az', 'Name A–Z'], ['name_za', 'Name Z–A'],
    ['quantity_desc', 'Quantity high–low'], ['quantity_asc', 'Quantity low–high'],
    ['set', 'Set'], ['number', 'Card number'], ['recent', 'Recently added'],
  ];
  sortSelect.replaceChildren(...options.map(([value, label]) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    return option;
  }));
  sortSelect.value = state.sort;
}

function updateActiveControls() {
  modeButtons.forEach((button) => button.classList.toggle('is-active', button.dataset.mode === state.mode));
  document.querySelectorAll('[data-category]').forEach((button) => {
    const active = state.recent ? button.dataset.category === 'recent' : button.dataset.category === state.category;
    button.classList.toggle('is-active', active && (button !== allButton || state.location === 'all'));
  });
  document.querySelectorAll('[data-location]').forEach((button) => {
    button.classList.toggle('is-active', String(button.dataset.location) === String(state.location));
  });
}

function visibleCards() {
  const query = state.query.trim().toLocaleLowerCase();
  return state.items.filter((card) => {
    if (cardLocationQuantity(card) <= 0) return false;
    if (!state.recent && state.category !== 'all' && !categoryMatches(card, state.category)) return false;
    if (state.set !== 'all' && card.set_code !== state.set) return false;
    if (!query) return true;
    return [
      card.name, card.set_name, card.set_code, card.number, collectorNumber(card),
      categoryLabel(card), isAceSpec(card) ? 'ACE SPEC' : '',
    ]
      .some((value) => String(value || '').toLocaleLowerCase().includes(query));
  });
}

function groupKey(card) {
  if (state.category === 'ace-spec') return 'ace-spec';
  if (state.mode === 'alpha') return card.name.slice(0, 1).toUpperCase() || '#';
  if (state.mode === 'set') return card.set_code;
  return categoryKey(card);
}

function groupTitle(card) {
  if (state.category === 'ace-spec') return 'ACE SPEC';
  if (state.mode === 'alpha') return card.name.slice(0, 1).toUpperCase() || '#';
  if (state.mode === 'set') return card.set_name;
  return categoryLabel(card);
}

function compareCards(left, right) {
  const name = left.name.localeCompare(right.name, undefined, {sensitivity: 'base'});
  const setName = left.set_name.localeCompare(right.set_name, undefined, {sensitivity: 'base'});
  const number = (left.number_numeric ?? Number.MAX_SAFE_INTEGER) - (right.number_numeric ?? Number.MAX_SAFE_INTEGER);
  if (state.sort === 'name_za') return -name || setName || number;
  if (state.sort === 'quantity_desc') return cardLocationQuantity(right) - cardLocationQuantity(left) || name;
  if (state.sort === 'quantity_asc') return cardLocationQuantity(left) - cardLocationQuantity(right) || name;
  if (state.sort === 'set') return setName || number || name;
  if (state.sort === 'number') return number || name;
  if (state.sort === 'recent') {
    return (inventoryDate(right.date_added)?.valueOf() || 0) - (inventoryDate(left.date_added)?.valueOf() || 0) || name;
  }
  return name || setName || number;
}

function orderedGroups(cards) {
  const grouped = new Map();
  for (const card of cards) {
    const key = groupKey(card);
    if (!grouped.has(key)) grouped.set(key, {title: groupTitle(card), cards: []});
    grouped.get(key).cards.push(card);
  }
  const groups = [...grouped.entries()];
  groups.forEach(([, group]) => group.cards.sort(compareCards));
  groups.sort(([leftKey, left], [rightKey, right]) => {
    if (state.mode === 'typing') return (CATEGORY_ORDER.get(leftKey) ?? 99) - (CATEGORY_ORDER.get(rightKey) ?? 99);
    return left.title.localeCompare(right.title, undefined, {numeric: true});
  });
  return groups;
}

function retryImageUrl(url, attempt) {
  if (!attempt) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}collection_retry=${attempt}`;
}

function pumpCardImageQueue() {
  while (activeCardImageLoads < CARD_IMAGE_MAX_CONCURRENT && cardImageQueue.length) {
    const request = cardImageQueue.shift();
    if (request.generation !== cardImageGeneration) continue;
    activeCardImageLoads += 1;
    let settled = false;
    const timeout = window.setTimeout(() => finish(false), CARD_IMAGE_TIMEOUT_MS);
    const finish = (loaded) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeout);
      activeCardImageLoads -= 1;
      request.image.onload = null;
      request.image.onerror = null;
      if (!request.image.isConnected || request.generation !== cardImageGeneration) {
        pumpCardImageQueue();
        return;
      }
      if (loaded) {
        request.art.classList.remove('image-loading', 'image-missing');
      } else if (request.attempt < CARD_IMAGE_MAX_RETRIES) {
        window.setTimeout(() => {
          if (request.image.isConnected && request.generation === cardImageGeneration) {
            cardImageQueue.push({...request, attempt: request.attempt + 1});
            pumpCardImageQueue();
          }
        }, 350 * (request.attempt + 1));
      } else {
        request.art.classList.remove('image-loading');
        request.art.classList.add('image-missing');
      }
      pumpCardImageQueue();
    };
    request.image.onload = () => finish(true);
    request.image.onerror = () => finish(false);
    request.image.src = retryImageUrl(request.url, request.attempt);
  }
}

function enqueueCardImage(image, art, url) {
  art.classList.add('image-loading');
  cardImageQueue.push({image, art, url, attempt: 0, generation: cardImageGeneration});
  pumpCardImageQueue();
}

function observeCardImage(image, art, url, priority) {
  if (!url) {
    art.classList.add('image-missing');
    return;
  }
  image.fetchPriority = priority ? 'high' : 'auto';
  if (priority || !('IntersectionObserver' in window)) {
    enqueueCardImage(image, art, url);
    return;
  }
  if (!cardImageObserver) {
    cardImageObserver = new IntersectionObserver((entries, observer) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        observer.unobserve(entry.target);
        enqueueCardImage(entry.target, entry.target._artContainer, entry.target.dataset.imageUrl);
      }
    }, {rootMargin: '700px 0px'});
  }
  image._artContainer = art;
  image.dataset.imageUrl = url;
  cardImageObserver.observe(image);
}

function resetCardImageLoading() {
  cardImageGeneration += 1;
  cardImageQueue.length = 0;
  cardImageObserver?.disconnect();
  cardImageObserver = null;
}

function selectionSource() {
  return state.location !== 'all' && state.location !== 'unassigned'
    ? String(state.location)
    : 'unassigned';
}

function availableAtSource(card, source = selectionSource()) {
  return source === 'unassigned'
    ? Number(card.unassigned_quantity || 0)
    : Number(card.locations?.[String(source)] || 0);
}

function updateSelectionToolbar() {
  const count = selectionState.quantities.size;
  selectionStart.hidden = selectionState.active;
  selectionActions.hidden = !selectionState.active;
  selectionCount.textContent = `${count} ${count === 1 ? 'card' : 'cards'} selected${selectionState.deckName ? ` for ${selectionState.deckName}` : ''}`;
  selectionMove.disabled = count === 0;
}

function startSelection(quantities = new Map(), deckName = '') {
  selectionState.active = true;
  selectionState.quantities = new Map(quantities);
  selectionState.deckName = deckName;
  closeDrawer();
  window.CardInspector?.close?.();
  updateSelectionToolbar();
  render();
}

function stopSelection() {
  selectionState.active = false;
  selectionState.quantities.clear();
  selectionState.deckName = '';
  updateSelectionToolbar();
  render();
}

function toggleCardSelection(card) {
  if (selectionState.quantities.has(card.id)) selectionState.quantities.delete(card.id);
  else selectionState.quantities.set(card.id, 1);
  updateSelectionToolbar();
  render();
}

function renderCollectionDecks() {
  if (!savedDecks.length) {
    collectionDecksStatus.textContent = 'No saved decks yet.';
    collectionDecks.replaceChildren();
    return;
  }
  collectionDecksStatus.textContent = '';
  const cards = savedDecks.map((deck) => {
    const button = document.createElement('button');
    button.className = 'binder-nav-item';
    button.type = 'button';
    button.dataset.deckId = String(deck.id);
    const icon = document.createElement('span');
    icon.className = 'binder-nav-icon';
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = '▱';
    const name = document.createElement('strong');
    name.textContent = deck.name;
    const count = document.createElement('b');
    count.textContent = String(deck.card_count);
    button.append(icon, name, count);
    button.addEventListener('click', () => void openDeckEditor(deck.id));
    return button;
  });
  collectionDecks.replaceChildren(...cards);
}

async function loadCollectionDecks() {
  try {
    const response = await fetch('/decks', {cache: 'no-store'});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'Saved decks could not be loaded.');
    savedDecks = data.decks || [];
    renderCollectionDecks();
  } catch (error) {
    collectionDecksStatus.textContent = error.message;
    collectionDecksStatus.classList.add('is-error');
  }
}

function parseDeckEditorEntries(text) {
  const entries = [];
  let section = 'trainer';
  for (const rawLine of String(text || '').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    const heading = line.match(/^(pok[eé]mon|trainer|energy)\s*:?\s*\d*$/i);
    if (heading) {
      section = heading[1].toLocaleLowerCase().startsWith('pok') ? 'pokemon' : heading[1].toLocaleLowerCase();
      continue;
    }
    const printed = line.match(/^(\d+)\s+(.+?)\s+([A-Za-z0-9-]{2,12})\s+(\S*\d\S*)$/);
    const named = line.match(/^(\d+)\s+(.+?)$/);
    if (!printed && !named) continue;
    entries.push({
      quantity: Number((printed || named)[1]),
      name: (printed || named)[2].trim(),
      set_code: printed ? printed[3].toUpperCase() : '',
      number: printed ? printed[4] : '',
      section,
      image_url: '',
    });
  }
  return entries;
}

function deckEntryKey(entry) {
  const name = String(entry.name || '').trim().toLocaleLowerCase();
  return entry.section === 'pokemon'
    ? `pokemon|${name}|${String(entry.set_code || '').toUpperCase()}|${String(entry.number || '').replace(/^0+(?=\d)/, '')}`
    : `${entry.section}|${name}`;
}

function serializeDeckEditorEntries(entries) {
  const groups = [
    ['pokemon', 'Pokémon'],
    ['trainer', 'Trainer'],
    ['energy', 'Energy'],
  ];
  return groups.map(([section, label]) => {
    const rows = entries.filter((entry) => entry.section === section);
    if (!rows.length) return '';
    const total = rows.reduce((sum, entry) => sum + entry.quantity, 0);
    return `${label}: ${total}\n${rows.map((entry) => {
      const printing = entry.set_code && entry.number ? ` ${entry.set_code} ${entry.number}` : '';
      return `${entry.quantity} ${entry.name}${printing}`;
    }).join('\n')}`;
  }).filter(Boolean).join('\n\n');
}

function deckEditorCardCount() {
  return deckEditorState.entries.reduce((sum, entry) => sum + entry.quantity, 0);
}

function setDeckEditorStatus(message, stateName = '') {
  deckEditorStatus.textContent = message;
  deckEditorStatus.className = `deck-editor-status${stateName ? ` is-${stateName}` : ''}`;
}

function renderDeckEditorEntries() {
  const deck = savedDecks.find((item) => item.id === deckEditorState.deckId);
  if (!deck) return;
  const total = deckEditorCardCount();
  deckEditorTotal.textContent = `${total} ${total === 1 ? 'card' : 'cards'}`;
  deckEditorSummary.textContent = `${deckEditorState.entries.length} unique ${deckEditorState.entries.length === 1 ? 'entry' : 'entries'} · Physical inventory is not changed here.`;
  const rows = deckEditorState.entries.map((entry, index) => {
    const article = document.createElement('article');
    article.className = 'deck-editor-entry';
    const art = document.createElement('button');
    art.className = `deck-editor-entry-art${entry.image_url ? '' : ' image-missing'}`;
    art.type = 'button';
    art.setAttribute('aria-label', `Inspect ${entry.name}`);
    if (entry.image_url) {
      const image = document.createElement('img');
      image.src = entry.image_url;
      image.alt = '';
      image.loading = 'lazy';
      art.append(image);
      art.addEventListener('click', () => window.CardInspector?.open?.(entry, art));
    }
    const identity = document.createElement('div');
    identity.className = 'deck-editor-entry-identity';
    const category = document.createElement('small');
    category.textContent = entry.section === 'pokemon' ? 'POKÉMON' : entry.section.toUpperCase();
    const name = document.createElement('strong');
    name.textContent = entry.name;
    const printing = document.createElement('span');
    printing.textContent = entry.set_code && entry.number ? `${entry.set_code} · ${entry.number}` : 'Any printing';
    identity.append(category, name, printing);
    const controls = document.createElement('div');
    controls.className = 'deck-editor-entry-controls';
    const minus = document.createElement('button');
    minus.type = 'button';
    minus.textContent = '−';
    minus.setAttribute('aria-label', `Remove one ${entry.name}`);
    const quantity = document.createElement('input');
    quantity.type = 'number';
    quantity.inputMode = 'numeric';
    quantity.min = '0';
    quantity.max = '60';
    quantity.value = String(entry.quantity);
    quantity.setAttribute('aria-label', `${entry.name} deck quantity`);
    const plus = document.createElement('button');
    plus.type = 'button';
    plus.textContent = '+';
    plus.setAttribute('aria-label', `Add one ${entry.name}`);
    const update = (value) => void updateDeckEntryQuantity(index, value);
    minus.addEventListener('click', () => update(Math.max(0, entry.quantity - 1)));
    plus.addEventListener('click', () => update(Math.min(60, entry.quantity + 1)));
    quantity.addEventListener('change', () => update(Number(quantity.value)));
    controls.append(minus, quantity, plus);
    article.append(art, identity, controls);
    return article;
  });
  if (!rows.length) {
    const empty = document.createElement('p');
    empty.className = 'deck-editor-empty';
    empty.textContent = 'This deck has no editable entries.';
    rows.push(empty);
  }
  deckEditorEntries.replaceChildren(...rows);
}

async function saveDeckEditorEntries(message) {
  const deck = savedDecks.find((item) => item.id === deckEditorState.deckId);
  if (!deck || !deckEditorState.entries.length) {
    setDeckEditorStatus('A saved deck must contain at least one card.', 'error');
    return false;
  }
  setDeckEditorStatus('Saving deck list…');
  deckEditorDialog.classList.add('is-saving');
  try {
    const data = await inventoryRequest('/decks/save', {
      id: deck.id,
      name: deck.name,
      deck_list: serializeDeckEditorEntries(deckEditorState.entries),
    });
    savedDecks = savedDecks.map((item) => item.id === data.deck.id ? data.deck : item);
    renderCollectionDecks();
    renderDeckEditorEntries();
    setDeckEditorStatus(message, 'saved');
    return true;
  } catch (error) {
    setDeckEditorStatus(error.message, 'error');
    return false;
  } finally {
    deckEditorDialog.classList.remove('is-saving');
  }
}

async function updateDeckEntryQuantity(index, requested) {
  const quantity = Number(requested);
  if (!Number.isInteger(quantity) || quantity < 0 || quantity > 60) {
    setDeckEditorStatus('Deck quantities must be whole numbers from 0 to 60.', 'error');
    renderDeckEditorEntries();
    return;
  }
  if (quantity === 0 && deckEditorState.entries.length === 1) {
    setDeckEditorStatus('A saved deck must keep at least one card. Remove the deck from the full deck library instead.', 'error');
    return;
  }
  const original = deckEditorState.entries.map((entry) => ({...entry}));
  const entry = deckEditorState.entries[index];
  if (!entry) return;
  if (quantity === 0) deckEditorState.entries.splice(index, 1);
  else entry.quantity = quantity;
  renderDeckEditorEntries();
  const saved = await saveDeckEditorEntries(quantity === 0 ? `${entry.name} was removed from the deck.` : `${entry.name} was updated to ${quantity}.`);
  if (!saved) {
    deckEditorState.entries = original;
    renderDeckEditorEntries();
  }
}

function catalogCardSection(card) {
  if (card.card_type === 'POKEMON') return 'pokemon';
  if (card.card_type === 'ENERGY') return 'energy';
  return 'trainer';
}

async function addCatalogCardToDeck(card) {
  const entry = {
    quantity: 1,
    name: card.name,
    set_code: card.set_code || '',
    number: card.number || '',
    section: catalogCardSection(card),
    image_url: card.image_url || '',
  };
  const key = deckEntryKey(entry);
  const existing = deckEditorState.entries.find((item) => deckEntryKey(item) === key);
  if (existing) {
    if (existing.quantity >= 60) {
      setDeckEditorStatus(`${existing.name} is already at the maximum deck quantity.`, 'error');
      return;
    }
    existing.quantity += 1;
    if (!existing.image_url) existing.image_url = entry.image_url;
  } else {
    deckEditorState.entries.push(entry);
  }
  renderDeckEditorEntries();
  const saved = await saveDeckEditorEntries(`${card.name} was added to the deck. Ownership was not changed.`);
  if (!saved) {
    if (existing) existing.quantity -= 1;
    else deckEditorState.entries = deckEditorState.entries.filter((item) => item !== entry);
    renderDeckEditorEntries();
  }
}

function renderDeckCatalogResults(cards, total) {
  if (!cards.length) {
    const empty = document.createElement('p');
    empty.className = 'deck-editor-empty';
    empty.textContent = 'No catalog cards matched that search.';
    deckEditorSearchResults.replaceChildren(empty);
    return;
  }
  const rows = cards.map((card) => {
    const article = document.createElement('article');
    const art = document.createElement('button');
    art.type = 'button';
    art.className = `deck-editor-result-art${card.image_url ? '' : ' image-missing'}`;
    if (card.image_url) {
      const image = document.createElement('img');
      image.src = card.image_url;
      image.alt = '';
      image.loading = 'lazy';
      art.append(image);
      art.addEventListener('click', () => window.CardInspector?.open?.(card, art));
    }
    const copy = document.createElement('div');
    const name = document.createElement('strong');
    name.textContent = card.name;
    const printing = document.createElement('span');
    printing.textContent = `${card.set_code} · ${card.number}${card.printed_total ? `/${card.printed_total}` : ''}`;
    const owned = document.createElement('small');
    owned.textContent = `${Number(card.quantity || 0)} owned`;
    copy.append(name, printing, owned);
    const add = document.createElement('button');
    add.type = 'button';
    add.textContent = 'Add';
    add.addEventListener('click', () => void addCatalogCardToDeck(card));
    article.append(art, copy, add);
    return article;
  });
  const notice = document.createElement('p');
  notice.className = 'deck-editor-result-count';
  notice.textContent = total > cards.length ? `Showing the first ${cards.length} of ${total}. Refine the search to narrow it down.` : `${total} matching ${total === 1 ? 'card' : 'cards'}.`;
  deckEditorSearchResults.replaceChildren(notice, ...rows);
}

async function searchDeckCatalog(event) {
  event.preventDefault();
  const query = deckEditorQuery.value.trim();
  const type = deckEditorType.value;
  if (!query && !type) {
    setDeckEditorStatus('Enter a card name or choose a card type before searching.', 'error');
    deckEditorQuery.focus();
    return;
  }
  setDeckEditorStatus('Searching the full local card catalog…');
  const parameters = new URLSearchParams({q: query, type, format: 'expanded', limit: '30', offset: '0'});
  try {
    const response = await fetch(`/catalog/search?${parameters}`, {cache: 'no-store'});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'Catalog search failed.');
    renderDeckCatalogResults(data.items || [], data.total || 0);
    setDeckEditorStatus('Choose Add beside any printing. Unowned cards are allowed.');
  } catch (error) {
    deckEditorSearchResults.replaceChildren();
    setDeckEditorStatus(error.message, 'error');
  }
}

async function hydrateDeckEditorArtwork(deck) {
  try {
    const data = await inventoryRequest('/deck/check', {deck_list: deck.deck_list});
    for (const item of [...(data.items || []), ...(data.ignored_basic_energy || [])]) {
      const match = deckEditorState.entries.find((entry) => deckEntryKey(entry) === deckEntryKey({
        name: item.name,
        set_code: item.set_code,
        number: item.number,
        section: item.deck_section,
      }));
      if (match && item.image_url) match.image_url = item.image_url;
    }
    renderDeckEditorEntries();
  } catch (_error) {
    // Editing remains available even when a legacy list cannot be fully checked.
  }
}

async function openDeckEditor(id) {
  const deck = savedDecks.find((item) => item.id === id);
  if (!deck) return;
  deckEditorState.deckId = id;
  deckEditorState.entries = parseDeckEditorEntries(deck.deck_list);
  deckEditorTitle.textContent = deck.name;
  deckEditorFullCheck.href = `/deck?deck=${deck.id}`;
  deckEditorSearchResults.replaceChildren();
  deckEditorQuery.value = '';
  deckEditorType.value = '';
  setDeckEditorStatus('Use −, +, or enter a quantity. Changes save immediately.');
  renderDeckEditorEntries();
  deckEditorDialog.showModal();
  await hydrateDeckEditorArtwork(deck);
}

async function prepareSavedDeck(deck, button) {
  button.disabled = true;
  button.textContent = 'Checking inventory…';
  collectionDecksStatus.textContent = `Matching ${deck.name} to your collection…`;
  try {
    const data = await inventoryRequest('/deck/check', {deck_list: deck.deck_list});
    const quantities = new Map();
    for (const item of data.items || []) {
      for (const fill of item.fills || []) {
        quantities.set(fill.card_id, (quantities.get(fill.card_id) || 0) + Number(fill.quantity || 0));
      }
    }
    if (!quantities.size) throw new Error('None of this deck’s matched cards are currently available in the collection.');
    startSelection(quantities, deck.name);
    openMoveDialog('deck');
    collectionDecksStatus.textContent = `${quantities.size} owned card printings prepared for ${deck.name}.`;
  } catch (error) {
    collectionDecksStatus.textContent = error.message;
    collectionDecksStatus.classList.add('is-error');
  } finally {
    button.disabled = false;
    button.textContent = 'Assign cards to deck box';
  }
}

function openMoveDialog(preferredAmount = 'one') {
  if (!selectionState.quantities.size) return;
  const source = selectionSource();
  const sourceOptions = [
    ['unassigned', 'Unassigned'],
    ...state.locations.map((location) => [String(location.id), location.name]),
  ];
  moveSource.replaceChildren(...sourceOptions.map(([value, label]) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    return option;
  }));
  moveSource.value = source;
  moveDestination.replaceChildren(...state.locations.map((location) => {
    const option = document.createElement('option');
    option.value = String(location.id);
    option.textContent = location.name;
    return option;
  }));
  const firstDestination = state.locations.find((location) => String(location.id) !== source);
  if (firstDestination) moveDestination.value = String(firstDestination.id);
  moveDeckOption.hidden = !selectionState.deckName;
  const amount = moveForm.querySelector(`input[name="move_amount"][value="${preferredAmount}"]`)
    || moveForm.querySelector('input[name="move_amount"][value="one"]');
  amount.checked = true;
  moveSummary.textContent = `${selectionState.quantities.size} selected card printings${selectionState.deckName ? ` for ${selectionState.deckName}` : ''}. Your total ownership will not change.`;
  moveStatus.textContent = state.locations.length ? '' : 'Create a location before moving cards.';
  moveForm.querySelector('button[type="submit"]').disabled = !state.locations.length;
  moveDialog.showModal();
}

async function moveSelectedCards(event) {
  event.preventDefault();
  const source = moveSource.value;
  const destination = moveDestination.value;
  if (!destination) {
    moveStatus.textContent = 'Create and choose a destination location first.';
    return;
  }
  if (source === destination) {
    moveStatus.textContent = 'Choose a different destination location.';
    return;
  }
  const mode = new FormData(moveForm).get('move_amount');
  const quantities = {};
  for (const [cardId, requested] of selectionState.quantities) {
    const card = state.items.find((item) => item.id === cardId);
    if (!card) continue;
    const available = availableAtSource(card, source);
    const alreadyAtDestination = Number(card.locations?.[String(destination)] || 0);
    const quantity = mode === 'all'
      ? available
      : mode === 'deck'
        ? Math.min(Math.max(0, requested - alreadyAtDestination), available)
        : Math.min(1, available);
    if (quantity > 0) quantities[cardId] = quantity;
  }
  if (!Object.keys(quantities).length) {
    moveStatus.textContent = 'None of the selected cards have copies available in that source.';
    return;
  }
  const submit = moveForm.querySelector('button[type="submit"]');
  submit.disabled = true;
  moveStatus.textContent = 'Moving cards…';
  try {
    const data = await inventoryRequest('/inventory/locations/move', {
      quantities,
      source_location_id: source,
      destination_location_id: destination,
    });
    moveDialog.close();
    selectionState.active = false;
    selectionState.quantities.clear();
    selectionState.deckName = '';
    await loadInventory();
    statusText.hidden = false;
    statusText.textContent = `Moved ${data.moved_copies} ${data.moved_copies === 1 ? 'copy' : 'copies'} across ${data.moved_unique_cards} selected cards.`;
  } catch (error) {
    moveStatus.textContent = error.message;
  } finally {
    submit.disabled = false;
    updateSelectionToolbar();
  }
}

function cardElement(card, prioritizeImage = false) {
  const tile = document.createElement('button');
  tile.className = 'binder-card';
  tile.type = 'button';
  tile.dataset.cardId = card.id;
  const visibleQuantity = cardLocationQuantity(card);
  tile.setAttribute('aria-label', `Open ${card.name}, ${collectorNumber(card)}, quantity ${visibleQuantity}`);
  tile.classList.toggle('is-selected', state.selectedId === card.id);
  tile.classList.toggle('is-selecting', selectionState.active);
  tile.classList.toggle('is-checked', selectionState.quantities.has(card.id));
  if (selectionState.active) tile.setAttribute('aria-pressed', String(selectionState.quantities.has(card.id)));

  const art = document.createElement('span');
  art.className = 'binder-card-art';
  art.title = 'Click artwork to enlarge';
  const image = document.createElement('img');
  image.decoding = 'async';
  image.alt = `${card.name} card`;
  observeCardImage(image, art, card.image_url, prioritizeImage);
  const quantity = document.createElement('b');
  quantity.className = 'binder-card-quantity';
  quantity.textContent = `× ${visibleQuantity}`;
  const check = document.createElement('span');
  check.className = 'binder-card-check';
  check.setAttribute('aria-hidden', 'true');
  check.textContent = selectionState.quantities.has(card.id) ? '✓' : '';
  art.append(image, quantity, check);

  const name = document.createElement('strong');
  name.textContent = card.name;
  const identity = document.createElement('small');
  identity.textContent = `${card.set_code}  •  ${collectorNumber(card)}`;
  tile.append(art, name, identity);
  tile.addEventListener('click', (event) => {
    if (selectionState.active) {
      toggleCardSelection(card);
      return;
    }
    if (event.target.closest('.binder-card-art')) {
      window.CardInspector.open(card, tile);
      return;
    }
    openDrawer(card);
  });
  return tile;
}

function renderAlphabet(groups) {
  if (state.mode !== 'alpha') {
    alphabetNavigation.hidden = true;
    alphabetNavigation.replaceChildren();
    return;
  }
  alphabetNavigation.hidden = false;
  const keys = new Set(groups.map(([key]) => key));
  const fragment = document.createDocumentFragment();
  for (const letter of 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = letter;
    button.disabled = !keys.has(letter);
    button.addEventListener('click', () => document.querySelector(`#group_${letter}`)?.scrollIntoView({behavior: 'smooth'}));
    fragment.append(button);
  }
  alphabetNavigation.replaceChildren(fragment);
}

function render() {
  resetCardImageLoading();
  updateActiveControls();
  updateSelectionToolbar();
  const cards = visibleCards();
  const copies = cards.reduce((sum, card) => sum + cardLocationQuantity(card), 0);
  const groups = orderedGroups(cards);

  const location = selectedLocation();
  const locationTitle = state.location === 'unassigned' ? 'Unassigned' : location?.name || '';

  viewEyebrow.textContent = state.location !== 'all'
    ? 'Storage location'
    : state.recent ? 'Scan history' : state.mode === 'set' ? 'Organized by set' : state.mode === 'alpha' ? 'Organized A–Z' : 'Organized by typing';
  viewTitle.textContent = state.recent
    ? 'Recently added'
    : state.location !== 'all'
      ? locationTitle
    : state.category !== 'all'
      ? CATEGORY_LABELS.get(state.category) || titleCase(state.category)
      : state.mode === 'set' ? 'Cards by set' : state.mode === 'alpha' ? 'Alphabetical collection' : 'All cards';
  viewCount.textContent = `${cards.length} unique ${cards.length === 1 ? 'card' : 'cards'}  •  ${copies} total ${copies === 1 ? 'copy' : 'copies'}`;

  renderAlphabet(groups);
  groupsContainer.replaceChildren();
  if (!state.items.length) {
    statusText.textContent = 'Your collection is empty. Use Search Cards to find cards and enter the quantities you own.';
    statusText.hidden = false;
    return;
  }
  if (!cards.length) {
    statusText.textContent = 'No cards in your inventory match these filters.';
    statusText.hidden = false;
    return;
  }
  statusText.hidden = true;

  const fragment = document.createDocumentFragment();
  let imageIndex = 0;
  for (const [key, group] of groups) {
    const section = document.createElement('section');
    section.className = 'binder-group';
    section.id = `group_${String(key).replace(/[^A-Za-z0-9_-]/g, '_')}`;
    const heading = document.createElement('div');
    heading.className = 'binder-group-heading';
    const title = document.createElement('h2');
    title.textContent = group.title;
    const count = document.createElement('span');
    count.textContent = `${group.cards.length} owned`;
    heading.append(title, count);
    const grid = document.createElement('div');
    grid.className = 'binder-grid';
    grid.append(...group.cards.map((card) => cardElement(card, imageIndex++ < CARD_IMAGE_PRIORITY_COUNT)));
    section.append(heading, grid);
    fragment.append(section);
  }
  groupsContainer.append(fragment);
}

function openDrawer(card) {
  state.selectedId = card.id;
  drawer._selectedCard = card;
  document.querySelectorAll('.binder-card').forEach((tile) => tile.classList.toggle('is-selected', tile.dataset.cardId === card.id));
  document.querySelector('#drawer_category').textContent = categoryLabel(card);
  document.querySelector('#drawer_name').textContent = card.name;
  const image = document.querySelector('#drawer_image');
  image.src = card.image_url || '';
  image.alt = `${card.name} card`;
  document.querySelector('#drawer_quantity').textContent = String(card.quantity);
  drawerQuantityInput.value = String(card.quantity);
  drawerQuantitySummary.textContent = `${card.quantity} ${card.quantity === 1 ? 'copy' : 'copies'}`;
  drawerQuantityFeedback.textContent = '';
  drawerQuantityFeedback.className = 'card-drawer-save-feedback';
  drawerQuantitySave.disabled = false;
  renderDrawerLocations(card);
  document.querySelector('#drawer_set').textContent = `${card.set_name} (${card.set_code})`;
  document.querySelector('#drawer_number').textContent = collectorNumber(card);
  document.querySelector('#drawer_type').textContent = categoryLabel(card);
  document.querySelector('#drawer_regulation').textContent = card.regulation_mark || 'Not recorded';
  const added = inventoryDate(card.date_added);
  document.querySelector('#drawer_added').textContent = added
    ? new Intl.DateTimeFormat(undefined, {dateStyle: 'medium'}).format(added)
    : 'Not recorded';
  drawer.setAttribute('aria-hidden', 'false');
  document.querySelector('.binder-app').classList.add('has-drawer');
}

function setDrawerLocationFeedback(message, stateName = '') {
  drawerLocationFeedback.textContent = message;
  drawerLocationFeedback.className = `card-drawer-save-feedback${stateName ? ` is-${stateName}` : ''}`;
}

function selectedDrawerLocation() {
  return state.locations.find((location) => String(location.id) === String(drawerLocationSelect.value)) || null;
}

function syncDrawerLocationQuantity() {
  const card = selectedCard();
  const location = selectedDrawerLocation();
  drawerLocationQuantity.value = String(location && card ? Number(card.locations?.[String(location.id)] || 0) : 0);
  drawerLocationQuantity.disabled = !location;
  drawerLocationSave.disabled = !location;
  setDrawerLocationFeedback('');
}

function renderDrawerLocations(card) {
  const previous = drawerLocationSelect.value;
  const options = state.locations.map((location) => {
    const option = document.createElement('option');
    option.value = String(location.id);
    option.textContent = location.name;
    return option;
  });
  if (!options.length) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'Create a location first';
    options.push(option);
  }
  drawerLocationSelect.replaceChildren(...options);
  if (state.locations.some((location) => String(location.id) === previous)) drawerLocationSelect.value = previous;
  drawerUnassignedSummary.textContent = `${card.unassigned_quantity || 0} unassigned`;

  const rows = state.locations
    .map((location) => ({location, quantity: Number(card.locations?.[String(location.id)] || 0)}))
    .filter((entry) => entry.quantity > 0)
    .map(({location, quantity}) => {
      const row = document.createElement('div');
      const name = document.createElement('span');
      name.textContent = location.name;
      const count = document.createElement('strong');
      count.textContent = String(quantity);
      row.append(name, count);
      return row;
    });
  if (!rows.length) {
    const empty = document.createElement('p');
    empty.textContent = 'No copies assigned to a location yet.';
    rows.push(empty);
  }
  drawerLocationAllocations.replaceChildren(...rows);
  syncDrawerLocationQuantity();
}

async function saveDrawerLocation() {
  const card = selectedCard();
  const location = selectedDrawerLocation();
  if (!card || !location) {
    setDrawerLocationFeedback('Create a location first.', 'error');
    return;
  }
  const quantity = Number(drawerLocationQuantity.value);
  if (!Number.isInteger(quantity) || quantity < 0 || quantity > 9999) {
    syncDrawerLocationQuantity();
    setDrawerLocationFeedback('Enter a whole number from 0 to 9999.', 'error');
    return;
  }
  drawerLocationSave.disabled = true;
  drawerLocationQuantity.disabled = true;
  setDrawerLocationFeedback('Saving…', 'saving');
  try {
    const result = await inventoryRequest('/inventory/locations/set-quantity', {
      card_id: card.id,
      location_id: location.id,
      quantity,
    });
    card.locations ||= {};
    if (result.allocation.quantity > 0) card.locations[String(location.id)] = result.allocation.quantity;
    else delete card.locations[String(location.id)];
    card.assigned_quantity = result.allocation.assigned_quantity;
    card.unassigned_quantity = result.allocation.unassigned_quantity;
    recalculateLocationCounts();
    renderLocationNavigation();
    renderCategoryNavigation();
    renderDrawerLocations(card);
    render();
    setDrawerLocationFeedback(`Saved: ${quantity} in ${location.name}`, 'saved');
  } catch (error) {
    syncDrawerLocationQuantity();
    setDrawerLocationFeedback(`Could not save: ${error.message}`, 'error');
  } finally {
    drawerLocationSave.disabled = !selectedDrawerLocation();
    drawerLocationQuantity.disabled = !selectedDrawerLocation();
  }
}

function selectedCard() {
  return state.items.find((card) => card.id === state.selectedId) || drawer._selectedCard || null;
}

function setDrawerQuantityFeedback(message, stateName = '') {
  drawerQuantityFeedback.textContent = message;
  drawerQuantityFeedback.className = `card-drawer-save-feedback${stateName ? ` is-${stateName}` : ''}`;
}

function adjustDrawerQuantity(delta) {
  const current = Number(drawerQuantityInput.value);
  const quantity = Number.isInteger(current) ? Math.max(0, Math.min(9999, current + delta)) : 0;
  drawerQuantityInput.value = String(quantity);
  setDrawerQuantityFeedback('');
}

async function saveDrawerQuantity() {
  const card = selectedCard();
  if (!card) return;
  const quantity = Number(drawerQuantityInput.value);
  if (!Number.isInteger(quantity) || quantity < 0 || quantity > 9999) {
    drawerQuantityInput.value = String(card.quantity);
    setDrawerQuantityFeedback('Enter a whole number from 0 to 9999.', 'error');
    return;
  }
  if (quantity === card.quantity) {
    setDrawerQuantityFeedback(`Already saved: ${quantity} owned`, 'saved');
    return;
  }
  if (quantity === 0 && card.quantity > 0 && !window.confirm(`Remove ${card.name} from your collection?`)) {
    drawerQuantityInput.value = String(card.quantity);
    setDrawerQuantityFeedback('Removal cancelled.');
    return;
  }
  drawerQuantitySave.disabled = true;
  drawerQuantityInput.disabled = true;
  drawerQuantityDecrease.disabled = true;
  drawerQuantityIncrease.disabled = true;
  setDrawerQuantityFeedback('Saving...', 'saving');
  try {
    const response = await fetch('/inventory/set-quantity', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({card_id: card.id, quantity}),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || 'Quantity update failed');
    card.quantity = result.inventory.quantity;
    card.unassigned_quantity = Math.max(0, card.quantity - Number(card.assigned_quantity || 0));
    drawerQuantityInput.value = String(card.quantity);
    drawerQuantitySummary.textContent = `${card.quantity} ${card.quantity === 1 ? 'copy' : 'copies'}`;
    document.querySelector('#drawer_quantity').textContent = String(card.quantity);
    const existingIndex = state.items.findIndex((item) => item.id === card.id);
    if (card.quantity === 0 && existingIndex >= 0) state.items.splice(existingIndex, 1);
    if (card.quantity > 0 && existingIndex < 0) state.items.push(card);
    recalculateLocationCounts();
    renderLocationNavigation();
    renderCategoryNavigation();
    renderSetOptions();
    render();
    if (card.quantity > 0) renderDrawerLocations(card);
    setDrawerQuantityFeedback(
      card.quantity === 0 ? 'Removed from collection.' : `Saved: ${card.quantity} owned`,
      'saved',
    );
  } catch (error) {
    drawerQuantityInput.value = String(card.quantity);
    setDrawerQuantityFeedback(`Could not save: ${error.message}`, 'error');
  } finally {
    drawerQuantitySave.disabled = false;
    drawerQuantityInput.disabled = false;
    drawerQuantityDecrease.disabled = false;
    drawerQuantityIncrease.disabled = false;
  }
}

function closeDrawer() {
  state.selectedId = null;
  drawer._selectedCard = null;
  drawer.setAttribute('aria-hidden', 'true');
  document.querySelector('.binder-app').classList.remove('has-drawer');
  document.querySelectorAll('.binder-card.is-selected').forEach((tile) => tile.classList.remove('is-selected'));
}

function chooseCategory(value) {
  state.recent = value === 'recent';
  state.category = state.recent ? 'all' : value;
  if (state.recent) {
    state.sort = 'recent';
    sortSelect.value = 'recent';
  }
  render();
}

function chooseLocation(value) {
  state.location = String(value);
  state.recent = false;
  state.category = 'all';
  renderCategoryNavigation();
  render();
}

function setLocationsStatus(message, stateName = '') {
  locationsStatus.textContent = message;
  locationsStatus.className = `inventory-locations-status${stateName ? ` is-${stateName}` : ''}`;
}

function renderLocationManager() {
  const rows = state.locations.map((location) => {
    const row = document.createElement('article');
    const summary = document.createElement('div');
    const name = document.createElement('strong');
    name.textContent = location.name;
    const counts = document.createElement('small');
    counts.textContent = `${location.unique_cards} unique cards · ${location.total_copies} total copies`;
    summary.append(name, counts);
    const actions = document.createElement('div');
    const rename = document.createElement('button');
    rename.type = 'button';
    rename.textContent = 'Rename';
    rename.addEventListener('click', () => void renameLocation(location));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'is-remove';
    remove.textContent = 'Remove';
    remove.addEventListener('click', () => void removeLocation(location));
    actions.append(rename, remove);
    row.append(summary, actions);
    return row;
  });
  if (!rows.length) {
    const empty = document.createElement('p');
    empty.className = 'inventory-locations-empty';
    empty.textContent = 'No locations yet. Add a deck box, binder, or shelf above.';
    rows.push(empty);
  }
  locationsList.replaceChildren(...rows);
}

function openLocationManager() {
  renderLocationManager();
  setLocationsStatus('Locations are optional. Your collection totals stay unchanged.');
  locationsDialog.showModal();
}

async function renameLocation(location) {
  const name = window.prompt('Rename this location:', location.name);
  if (name === null) return;
  try {
    await inventoryRequest('/inventory/locations/rename', {location_id: location.id, name});
    await loadInventory({reopenDrawer: true});
    renderLocationManager();
    setLocationsStatus(`Renamed to ${name.trim()}.`, 'saved');
  } catch (error) {
    setLocationsStatus(error.message, 'error');
  }
}

async function removeLocation(location) {
  if (!window.confirm(`Remove ${location.name}? Its ${location.total_copies} assigned copies will return to Unassigned. Collection totals will not change.`)) return;
  try {
    const result = await inventoryRequest('/inventory/locations/remove', {location_id: location.id});
    if (String(state.location) === String(location.id)) state.location = 'all';
    await loadInventory({reopenDrawer: true});
    renderLocationManager();
    setLocationsStatus(`Removed ${location.name}. ${result.released_copies} copies returned to Unassigned.`, 'saved');
  } catch (error) {
    setLocationsStatus(error.message, 'error');
  }
}

async function createLocation(event) {
  event.preventDefault();
  const name = locationNameInput.value.trim();
  if (!name) return;
  try {
    await inventoryRequest('/inventory/locations/create', {name});
    locationNameInput.value = '';
    await loadInventory({reopenDrawer: true});
    renderLocationManager();
    setLocationsStatus(`Added ${name}.`, 'saved');
  } catch (error) {
    setLocationsStatus(error.message, 'error');
  }
}

function selectedImportMode() {
  return document.querySelector('input[name="inventory_import_mode"]:checked')?.value || 'update';
}

function setImportStatus(message, stateName = '') {
  importStatus.textContent = message;
  importStatus.className = `collection-import-status${stateName ? ` is-${stateName}` : ''}`;
}

function invalidateImportPreview(message = 'Preview the file to review its changes.') {
  importState.preview = null;
  importState.page = 1;
  importResults.hidden = true;
  importApply.disabled = true;
  setImportStatus(message);
}

function filteredImportChanges() {
  if (!importState.preview) return [];
  const type = importChangeFilter.value;
  const query = importSearch.value.trim().toLocaleLowerCase();
  return importState.preview.changes.filter((item) => {
    if (type !== 'all' && item.change !== type) return false;
    if (!query) return true;
    return [item.name, item.set_name, item.set_code, item.number, item.card_id]
      .some((value) => String(value || '').toLocaleLowerCase().includes(query));
  });
}

function importChangeLabel(change) {
  if (change === 'addition') return 'Add';
  if (change === 'removal') return 'Remove';
  return 'Change';
}

function renderImportChanges() {
  const changes = filteredImportChanges();
  const pageCount = Math.max(1, Math.ceil(changes.length / IMPORT_PREVIEW_PAGE_SIZE));
  importState.page = Math.min(importState.page, pageCount);
  const start = (importState.page - 1) * IMPORT_PREVIEW_PAGE_SIZE;
  const pageItems = changes.slice(start, start + IMPORT_PREVIEW_PAGE_SIZE);
  const fragment = document.createDocumentFragment();
  for (const item of pageItems) {
    const row = document.createElement('article');
    row.className = `collection-import-change is-${item.change}`;
    const label = document.createElement('b');
    label.textContent = importChangeLabel(item.change);
    const identity = document.createElement('div');
    const name = document.createElement('strong');
    name.textContent = item.name;
    const printing = document.createElement('small');
    printing.textContent = `${item.set_code || item.set_name} · ${item.number}${item.printed_total ? `/${item.printed_total}` : ''}`;
    identity.append(name, printing);
    const cardId = document.createElement('code');
    cardId.textContent = item.card_id;
    const quantity = document.createElement('div');
    quantity.className = 'quantity';
    const oldQuantity = document.createTextNode(String(item.old_quantity));
    const arrow = document.createElement('span');
    arrow.textContent = '→';
    const newQuantity = document.createTextNode(String(item.new_quantity));
    quantity.append(oldQuantity, arrow, newQuantity);
    row.append(label, identity, cardId, quantity);
    fragment.append(row);
  }
  if (!pageItems.length) {
    const empty = document.createElement('p');
    empty.className = 'collection-import-empty';
    empty.textContent = importState.preview?.changes.length
      ? 'No affected cards match this preview filter.'
      : 'This file would not change the collection.';
    fragment.append(empty);
  }
  importChanges.replaceChildren(fragment);
  importPage.textContent = `${changes.length} affected · Page ${importState.page} of ${pageCount}`;
  importPrevious.disabled = importState.page <= 1;
  importNext.disabled = importState.page >= pageCount;
}

function renderImportPreview(preview) {
  const summary = preview.summary;
  document.querySelector('#import_count_affected').textContent = String(summary.affected_cards);
  document.querySelector('#import_count_additions').textContent = String(summary.additions);
  document.querySelector('#import_count_changes').textContent = String(summary.quantity_changes);
  document.querySelector('#import_count_removals').textContent = String(summary.removals);
  document.querySelector('#import_count_unchanged').textContent = String(summary.unchanged);
  document.querySelector('#import_count_total').textContent = String(summary.total_after);
  importErrors.hidden = !preview.errors.length;
  importErrors.replaceChildren(...preview.errors.map((message) => {
    const paragraph = document.createElement('p');
    paragraph.textContent = message;
    return paragraph;
  }));
  importResults.hidden = false;
  importApply.disabled = !preview.can_apply || summary.affected_cards === 0;
  importApply.textContent = preview.mode === 'replace' ? 'Restore this collection' : 'Apply listed updates';
  importState.page = 1;
  renderImportChanges();
}

async function previewInventoryImport() {
  const file = importFile.files?.[0];
  if (!file) {
    setImportStatus('Choose a CSV or JSON collection export first.', 'error');
    return;
  }
  if (file.size > 20 * 1024 * 1024) {
    setImportStatus('That file is too large. Collection imports are limited to 20 MB.', 'error');
    return;
  }
  importPreviewButton.disabled = true;
  importApply.disabled = true;
  setImportStatus(`Validating ${file.name}…`);
  try {
    const content = await file.text();
    const response = await fetch('/inventory/import/preview', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({filename: file.name, content, mode: selectedImportMode()}),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || 'The collection file could not be previewed.');
    importState.content = content;
    importState.filename = file.name;
    importState.preview = result;
    renderImportPreview(result);
    setImportStatus(
      result.can_apply
        ? `${result.summary.affected_cards} affected cards found. Review the summary before applying.`
        : `${result.errors.length} import ${result.errors.length === 1 ? 'error needs' : 'errors need'} attention.`,
      result.can_apply ? '' : 'error',
    );
  } catch (error) {
    invalidateImportPreview();
    setImportStatus(error.message, 'error');
  } finally {
    importPreviewButton.disabled = false;
  }
}

async function applyInventoryImport() {
  const preview = importState.preview;
  if (!preview?.can_apply || !preview.summary.affected_cards) return;
  const warning = preview.mode === 'replace'
    ? `Restore from ${preview.filename}? This changes ${preview.summary.affected_cards} cards and removes ${preview.summary.removals}. A backup will be created first.`
    : `Apply ${preview.summary.affected_cards} listed card changes from ${preview.filename}? Cards absent from the file will stay unchanged.`;
  if (!window.confirm(warning)) return;
  importApply.disabled = true;
  importPreviewButton.disabled = true;
  setImportStatus('Creating a backup and applying the collection import…');
  try {
    const response = await fetch('/inventory/import/apply', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        filename: importState.filename,
        content: importState.content,
        mode: preview.mode,
        preview_id: preview.preview_id,
      }),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || 'The collection import could not be applied.');
    setImportStatus(`Import complete: ${result.applied_cards} card quantities updated.`, 'saved');
    importState.preview = null;
    importApply.disabled = true;
    await loadInventory();
  } catch (error) {
    setImportStatus(error.message, 'error');
    importApply.disabled = false;
  } finally {
    importPreviewButton.disabled = false;
  }
}

categoryNavigation.addEventListener('click', (event) => {
  const button = event.target.closest('[data-category]');
  if (button) chooseCategory(button.dataset.category);
});
allButton.addEventListener('click', () => {
  state.location = 'all';
  chooseCategory('all');
  renderCategoryNavigation();
});
document.querySelector('[data-location="unassigned"]').addEventListener('click', () => chooseLocation('unassigned'));
locationNavigation.addEventListener('click', (event) => {
  const button = event.target.closest('[data-location]');
  if (button) chooseLocation(button.dataset.location);
});
recentButton.addEventListener('click', () => chooseCategory('recent'));

modeButtons.forEach((button) => button.addEventListener('click', () => {
  state.mode = button.dataset.mode;
  state.recent = false;
  state.sort = state.mode === 'set' ? 'number' : 'name_az';
  sortSelect.value = state.sort;
  render();
}));

let searchFrame = null;
searchInput.addEventListener('input', () => {
  cancelAnimationFrame(searchFrame);
  searchFrame = requestAnimationFrame(() => {
    state.query = searchInput.value;
    render();
  });
});
sortSelect.addEventListener('change', () => { state.sort = sortSelect.value; render(); });
setFilter.addEventListener('change', () => { state.set = setFilter.value; render(); });
exportCsv.addEventListener('click', (event) => prepareCollectionExport(event, 'csv'));
exportJson.addEventListener('click', (event) => prepareCollectionExport(event, 'json'));
drawerClose.addEventListener('click', closeDrawer);
document.querySelector('#drawer_image_button').addEventListener('click', (event) => {
  const card = selectedCard();
  if (card) window.CardInspector.open(card, event.currentTarget);
});
drawerQuantityDecrease.addEventListener('click', () => adjustDrawerQuantity(-1));
drawerQuantityIncrease.addEventListener('click', () => adjustDrawerQuantity(1));
drawerQuantitySave.addEventListener('click', saveDrawerQuantity);
drawerQuantityInput.addEventListener('keydown', (event) => {
  if (event.key !== 'Enter') return;
  event.preventDefault();
  void saveDrawerQuantity();
});
drawerLocationSelect.addEventListener('change', syncDrawerLocationQuantity);
drawerLocationSave.addEventListener('click', saveDrawerLocation);
drawerLocationQuantity.addEventListener('keydown', (event) => {
  if (event.key !== 'Enter') return;
  event.preventDefault();
  void saveDrawerLocation();
});
locationManage.addEventListener('click', openLocationManager);
drawerLocationManage.addEventListener('click', openLocationManager);
deckEditorClose.addEventListener('click', () => deckEditorDialog.close());
deckEditorDialog.addEventListener('click', (event) => { if (event.target === deckEditorDialog) deckEditorDialog.close(); });
deckEditorSearchForm.addEventListener('submit', (event) => void searchDeckCatalog(event));
deckEditorAssign.addEventListener('click', () => {
  const deck = savedDecks.find((item) => item.id === deckEditorState.deckId);
  if (!deck) return;
  deckEditorDialog.close();
  void prepareSavedDeck(deck, deckEditorAssign);
});
locationsClose.addEventListener('click', () => locationsDialog.close());
locationsDialog.addEventListener('click', (event) => { if (event.target === locationsDialog) locationsDialog.close(); });
locationCreateForm.addEventListener('submit', (event) => void createLocation(event));
selectionStart.addEventListener('click', () => startSelection());
selectionAll.addEventListener('click', () => {
  for (const card of visibleCards()) {
    if (availableAtSource(card) > 0) selectionState.quantities.set(card.id, 1);
  }
  updateSelectionToolbar();
  render();
});
selectionClear.addEventListener('click', () => {
  selectionState.quantities.clear();
  updateSelectionToolbar();
  render();
});
selectionMove.addEventListener('click', () => openMoveDialog());
selectionCancel.addEventListener('click', stopSelection);
moveClose.addEventListener('click', () => moveDialog.close());
moveDialog.addEventListener('click', (event) => { if (event.target === moveDialog) moveDialog.close(); });
moveForm.addEventListener('submit', (event) => void moveSelectedCards(event));
moveManage.addEventListener('click', () => {
  moveDialog.close();
  openLocationManager();
});
document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeDrawer(); });
importOpen.addEventListener('click', () => importDialog.showModal());
importClose.addEventListener('click', () => importDialog.close());
importDialog.addEventListener('click', (event) => { if (event.target === importDialog) importDialog.close(); });
importFile.addEventListener('change', () => invalidateImportPreview(importFile.files?.[0] ? 'File selected. Preview it before applying.' : 'Choose an exported CSV or JSON file to begin.'));
document.querySelectorAll('input[name="inventory_import_mode"]').forEach((input) => input.addEventListener('change', () => invalidateImportPreview('Import method changed. Preview the file again.')));
importPreviewButton.addEventListener('click', () => void previewInventoryImport());
importApply.addEventListener('click', () => void applyInventoryImport());
importChangeFilter.addEventListener('change', () => { importState.page = 1; renderImportChanges(); });
importSearch.addEventListener('input', () => { importState.page = 1; renderImportChanges(); });
importPrevious.addEventListener('click', () => { importState.page -= 1; renderImportChanges(); });
importNext.addEventListener('click', () => { importState.page += 1; renderImportChanges(); });

async function loadInventory({reopenDrawer = false} = {}) {
  const selectedId = state.selectedId;
  try {
    const response = await fetch('/inventory/cards?sort=name', {cache: 'no-store'});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'Inventory could not be loaded.');
    state.items = data.items;
    state.locations = data.locations || [];
    state.unassigned = data.unassigned || {unique_cards: 0, total_copies: 0};
    if (state.location !== 'all' && state.location !== 'unassigned'
        && !state.locations.some((location) => String(location.id) === String(state.location))) {
      state.location = 'all';
    }
    recalculateLocationCounts();
    renderLocationNavigation();
    renderCategoryNavigation();
    renderSetOptions();
    setSortOptions();
    render();
    if (reopenDrawer && selectedId) {
      const selected = state.items.find((card) => card.id === selectedId);
      if (selected) openDrawer(selected);
      else closeDrawer();
    }
  } catch (error) {
    statusText.textContent = error.message;
    statusText.hidden = false;
  }
}

void Promise.all([loadInventory(), loadCollectionDecks()]);
