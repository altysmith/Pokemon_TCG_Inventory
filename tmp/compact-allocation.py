from pathlib import Path
p=Path('web/inventory.js');s=p.read_text(encoding='utf-8')
a=s.index('function deckViewStatus(item)');b=s.index('\nfunction deckViewCard',a)
s=s[:a]+'''function allocationBadge(item) {
  const assigned = Number(item.allocation?.assigned || 0);
  const needed = Math.max(0, item.requested - assigned);
  const prefix = `${assigned}/${item.requested}`;
  const missing = Number(item.missing || 0);
  const other = Number(item.allocation?.reserved || 0);
  const free = Math.max(0, Number(item.allocation?.available || 0) - assigned);
  if (!needed) return {text: `${prefix} allocated`, tone: 'ready'};
  if (missing >= needed) return {text: `${prefix} · ${needed} missing`, tone: 'missing'};
  if (free >= needed) return {text: `${prefix} · ${needed} available`, tone: 'available'};
  if (other >= needed) return {text: `${prefix} · ${needed} in other decks`, tone: 'reserved'};
  return {text: `${prefix} · Review sources`, tone: 'mixed'};
}

function deckViewStatus(item) {
  if (item.status === 'ignored') return 'Basic Energy · not checked';
  if (item.status === 'unresolved') return 'Needs review';
  if (item.allocation) return allocationBadge(item).text;
  return item.missing ? `${item.missing} missing from collection` : `${item.covered || 0} owned`;
}
''' +s[b:]
s=s.replace("const tile = document.createElement('button');\n  const ready = item.allocation", "const tile = document.createElement('article');\n  const ready = item.allocation",1)
s=s.replace("  tile.type = 'button';\n  tile.setAttribute('aria-label', `Inspect ${item.name}, ${item.requested} in deck, ${deckViewStatus(item)}`);\n  const art = document.createElement('span');", "  const art = document.createElement('button');\n  art.type = 'button';\n  art.setAttribute('aria-label', `Enlarge ${item.name}`);",1)
s=s.replace("  const status = document.createElement('span');\n  status.className = 'deck-view-card-status';", "  const status = document.createElement(item.allocation ? 'button' : 'span');\n  status.className = 'deck-view-card-status';\n  if (item.allocation) {\n    status.type = 'button';\n    status.dataset.tone = allocationBadge(item).tone;\n    status.setAttribute('aria-label', `${item.name}: ${deckViewStatus(item)}. Review allocations`);\n    status.addEventListener('click', () => openCollectionAllocation(item, status));\n  }",1)
s=s.replace("if (item.image_url) tile.addEventListener('click', () => window.CardInspector?.open?.(item, tile));", "if (item.image_url) art.addEventListener('click', () => window.CardInspector?.open?.(item, art));\n  else art.disabled = true;",1)
s=s.replace("const allocations = document.createElement('section');\n  allocations.className = 'collection-allocation-summary';\n  const allocationTitle = document.createElement('h2');", "const allocations = document.createElement('details');\n  allocations.className = 'collection-allocation-summary';\n  const allocationTitle = document.createElement('summary');")
s=s.replace("shortages.length ? 'Cards needing allocation' : 'All checked cards are allocated'", "shortages.length ? `${shortages.length} card types need allocation · Review` : 'All checked cards are allocated'")
p.write_text(s,encoding='utf-8')
