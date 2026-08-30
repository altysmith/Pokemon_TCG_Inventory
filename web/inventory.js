const groupsContainer = document.querySelector('#inventory_groups');
const statusText = document.querySelector('#inventory_status');
const searchInput = document.querySelector('#inventory_search');
const sortSelect = document.querySelector('#inventory_sort');
const setFilter = document.querySelector('#set_filter');
const modeButtons = [...document.querySelectorAll('[data-mode]')];
const categoryNavigation = document.querySelector('#category_navigation');
const allButton = document.querySelector('[data-category="all"]');
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

const CARD_IMAGE_MAX_CONCURRENT = 6;
const CARD_IMAGE_MAX_RETRIES = 2;
const CARD_IMAGE_PRIORITY_COUNT = 18;
const CARD_IMAGE_TIMEOUT_MS = 7000;
const cardImageQueue = [];
let activeCardImageLoads = 0;
let cardImageObserver = null;
let cardImageGeneration = 0;

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
  for (const card of state.items) {
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
    button.classList.toggle('is-active', active);
  });
}

function visibleCards() {
  const query = state.query.trim().toLocaleLowerCase();
  return state.items.filter((card) => {
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
  if (state.sort === 'quantity_desc') return right.quantity - left.quantity || name;
  if (state.sort === 'quantity_asc') return left.quantity - right.quantity || name;
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
  tile.setAttribute('aria-label', `Open ${card.name}, ${collectorNumber(card)}, quantity ${card.quantity}`);
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
  quantity.textContent = `× ${card.quantity}`;
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
  const copies = cards.reduce((sum, card) => sum + card.quantity, 0);
  const groups = orderedGroups(cards);

  viewEyebrow.textContent = state.recent ? 'Scan history' : state.mode === 'set' ? 'Organized by set' : state.mode === 'alpha' ? 'Organized A–Z' : 'Organized by typing';
  viewTitle.textContent = state.recent
    ? 'Recently added'
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
    drawerQuantityInput.value = String(card.quantity);
    drawerQuantitySummary.textContent = `${card.quantity} ${card.quantity === 1 ? 'copy' : 'copies'}`;
    document.querySelector('#drawer_quantity').textContent = String(card.quantity);
    const existingIndex = state.items.findIndex((item) => item.id === card.id);
    if (card.quantity === 0 && existingIndex >= 0) state.items.splice(existingIndex, 1);
    if (card.quantity > 0 && existingIndex < 0) state.items.push(card);
    renderCategoryNavigation();
    renderSetOptions();
    render();
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

categoryNavigation.addEventListener('click', (event) => {
  const button = event.target.closest('[data-category]');
  if (button) chooseCategory(button.dataset.category);
});
allButton.addEventListener('click', () => chooseCategory('all'));
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
document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeDrawer(); });

async function loadInventory() {
  try {
    const response = await fetch('/inventory/cards?sort=name', {cache: 'no-store'});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'Inventory could not be loaded.');
    state.items = data.items;
    renderCategoryNavigation();
    renderSetOptions();
    setSortOptions();
    render();
  } catch (error) {
    statusText.textContent = error.message;
    statusText.hidden = false;
  }
}

loadInventory();
