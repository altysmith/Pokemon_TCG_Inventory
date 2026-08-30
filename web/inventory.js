const groupsContainer = document.querySelector('#inventory_groups');
const statusText = document.querySelector('#inventory_status');
const searchInput = document.querySelector('#inventory_search');
const sortSelect = document.querySelector('#inventory_sort');
const setFilter = document.querySelector('#set_filter');
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

function cardElement(card, prioritizeImage = false) {
  const tile = document.createElement('button');
  tile.className = 'binder-card';
  tile.type = 'button';
  tile.dataset.cardId = card.id;
  const visibleQuantity = cardLocationQuantity(card);
  tile.setAttribute('aria-label', `Open ${card.name}, ${collectorNumber(card)}, quantity ${visibleQuantity}`);
  tile.classList.toggle('is-selected', state.selectedId === card.id);

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
  art.append(image, quantity);

  const name = document.createElement('strong');
  name.textContent = card.name;
  const identity = document.createElement('small');
  identity.textContent = `${card.set_code}  •  ${collectorNumber(card)}`;
  tile.append(art, name, identity);
  tile.addEventListener('click', (event) => {
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
locationsClose.addEventListener('click', () => locationsDialog.close());
locationsDialog.addEventListener('click', (event) => { if (event.target === locationsDialog) locationsDialog.close(); });
locationCreateForm.addEventListener('submit', (event) => void createLocation(event));
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

loadInventory();
