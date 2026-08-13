const sortSelect = document.querySelector('#inventory_sort');
const groupsContainer = document.querySelector('#inventory_groups');
const statusText = document.querySelector('#inventory_status');
const totalCopies = document.querySelector('#total_copies');
const uniqueCards = document.querySelector('#unique_cards');

function titleCase(value) {
  return String(value || '').toLowerCase().replace(/(^|_)([a-z])/g, (_match, space, letter) => `${space ? ' ' : ''}${letter.toUpperCase()}`);
}

function groupLabel(card, sort) {
  if (sort === 'set_number') return `${card.set_name} (${card.set_code})`;
  if (sort === 'category') return titleCase(card.card_type);
  if (sort === 'subtype') return card.display_subtype || titleCase(card.card_type);
  if (sort === 'element') return card.element_group;
  return card.name.slice(0, 1).toUpperCase() || '#';
}

function cardElement(card) {
  const article = document.createElement('article');
  article.className = 'collection-card';

  const image = document.createElement('img');
  image.loading = 'lazy';
  image.alt = `${card.name} card`;
  if (card.image_url) image.src = card.image_url;
  article.append(image);

  const body = document.createElement('div');
  body.className = 'collection-card-body';
  const name = document.createElement('strong');
  name.textContent = card.name;
  const identity = document.createElement('span');
  identity.textContent = `${card.set_code} ${card.number}${card.printed_total ? `/${card.printed_total}` : ''}`;
  const classifications = document.createElement('small');
  const details = [titleCase(card.card_type), card.display_subtype, ...card.types.map(titleCase)].filter(Boolean);
  classifications.textContent = details.join(' / ');
  body.append(name, identity, classifications);

  const quantity = document.createElement('b');
  quantity.className = 'collection-card-quantity';
  quantity.textContent = `x${card.quantity}`;
  quantity.title = `${card.quantity} in collection`;
  article.append(body, quantity);
  return article;
}

function render(data) {
  groupsContainer.replaceChildren();
  totalCopies.textContent = String(data.total_copies);
  uniqueCards.textContent = String(data.unique_cards);
  if (!data.items.length) {
    statusText.textContent = 'Your collection is empty. Add an exact card match from the scanner first.';
    return;
  }
  statusText.textContent = 'Read-only view. Sorting never changes inventory quantities.';
  let currentLabel = null;
  let grid = null;
  for (const card of data.items) {
    const label = groupLabel(card, data.sort);
    if (label !== currentLabel) {
      currentLabel = label;
      const section = document.createElement('section');
      section.className = 'collection-group';
      const heading = document.createElement('h2');
      heading.textContent = label;
      grid = document.createElement('div');
      grid.className = 'collection-grid';
      section.append(heading, grid);
      groupsContainer.append(section);
    }
    grid.append(cardElement(card));
  }
}

async function loadInventory() {
  statusText.textContent = 'Loading your local collection...';
  try {
    const response = await fetch(`/inventory/cards?sort=${encodeURIComponent(sortSelect.value)}`, {cache: 'no-store'});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'Inventory could not be loaded.');
    render(data);
  } catch (error) {
    statusText.textContent = error.message;
  }
}

sortSelect.addEventListener('change', loadInventory);
loadInventory();
