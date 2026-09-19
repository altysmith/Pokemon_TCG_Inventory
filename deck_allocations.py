"""Read-only deck availability and explicit, atomic allocation transfers."""
from deck_checker import check_deck_list, compatible_assignment_cards


def check_allocations(text, deck_id, catalog_path, inventory_path, connection, owned):
    decks = {row['id']: dict(row) for row in connection.execute(
        'SELECT id, name, deck_list FROM saved_decks WHERE archived_at IS NULL')}
    if deck_id and deck_id not in decks:
        raise ValueError('That saved deck no longer exists.')
    rows = [dict(row) for row in connection.execute(
        'SELECT a.* FROM saved_deck_assignments a JOIN saved_decks d ON d.id=a.deck_id WHERE d.archived_at IS NULL')]
    original_rows = [dict(row) for row in rows]
    current, totals = {}, {}
    for row in rows:
        card = row['card_id']
        totals[card] = totals.get(card, 0) + row['quantity']
        if row['deck_id'] == deck_id:
            current[card] = row['quantity']
    free = {card: max(0, quantity - totals.get(card, 0)) for card, quantity in owned.items()}
    preferred = {card: min(owned.get(card, 0), current.get(card, 0) + free.get(card, 0))
                 for card in dict.fromkeys([*current, *owned])}
    result = check_deck_list(text, catalog_path=catalog_path, inventory_path=inventory_path,
                             inventory_quantities=owned, preferred_card_quantities=preferred)
    remaining_current = dict(current)
    remaining_free = dict(free)
    for index, item in enumerate(result['items']):
        sources = []
        allocated = 0
        for fill in item['fills']:
            card, needed = fill['card_id'], fill['quantity']
            used = min(needed, remaining_current.get(card, 0))
            allocated += used
            remaining_current[card] = remaining_current.get(card, 0) - used
            needed -= used
            take = min(needed, remaining_free.get(card, 0))
            if take:
                sources.append({'deck_id': 0, 'deck_name': 'Unallocated copies', 'card_id': card, 'quantity': take})
                remaining_free[card] -= take
                needed -= take
            for row in rows:
                if not needed:
                    break
                if row['deck_id'] == deck_id or row['card_id'] != card:
                    continue
                take = min(needed, row['quantity'])
                if take:
                    sources.append({'deck_id': row['deck_id'], 'deck_name': decks[row['deck_id']]['name'],
                                    'card_id': card, 'quantity': take})
                    row['quantity'] -= take
                    needed -= take
        reserved = sum(source['quantity'] for source in sources if source['deck_id'])
        item['allocation'] = {'index': index, 'assigned': allocated, 'reserved': reserved,
                              'available': item['covered'] - reserved, 'sources': sources,
                              'editable': bool(deck_id and decks[deck_id]['deck_list'].strip() == text.strip())}
    # Sources are alternatives, not an automatically selected borrowing plan.
    for item in result['items']:
        allocation = item['allocation']
        deficit = max(0, item['requested'] - allocation['assigned'])
        choices = []
        if deficit and item['fills']:
            compatible = compatible_assignment_cards(catalog_path, item['fills'][0]['card_id'], set(owned))
            for card in compatible:
                card_id = card['id']
                free_count = min(deficit, free.get(card_id, 0))
                if free_count:
                    choices.append({'deck_id': 0, 'deck_name': 'Unallocated copies', 'card_id': card_id,
                                    'quantity': free_count, 'printing': f"{card['set_code']} · {card['number']}"})
                for row in original_rows:
                    if row['deck_id'] == deck_id or row['card_id'] != card_id:
                        continue
                    quantity = min(deficit, row['quantity'], max(0, owned.get(card_id, 0) - current.get(card_id, 0)))
                    if quantity:
                        choices.append({'deck_id': row['deck_id'], 'deck_name': decks[row['deck_id']]['name'],
                                        'card_id': card_id, 'quantity': quantity,
                                        'allocated_quantity': row['quantity'],
                                        'printing': f"{card['set_code']} · {card['number']}"})
        choices.sort(key=lambda source: (source['deck_id'] != 0, source['deck_name'].casefold(), source['card_id']))
        allocation['sources'] = choices
    result['summary']['reserved_cards'] = sum(item['allocation']['reserved'] for item in result['items'])
    result['summary']['available_cards'] = result['summary']['covered_cards'] - result['summary']['reserved_cards']
    return result


def transfer_allocation(database, inventory, catalog_path, inventory_path, data):
    deck_id = int(data.get('id', 0))
    source_id = int(data.get('source_deck_id', 0))
    index = int(data.get('item_index', -1))
    quantity = int(data.get('quantity', 0))
    card_id = str(data.get('card_id', ''))
    if deck_id <= 0 or quantity <= 0 or source_id < 0 or source_id == deck_id:
        raise ValueError('Choose a valid allocation and quantity.')
    database.initialize()
    with database.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        owned = {holding.card_id: holding.quantity for holding in inventory.holdings()}
        deck = connection.execute('SELECT deck_list FROM saved_decks WHERE id=? AND archived_at IS NULL', (deck_id,)).fetchone()
        if not deck or deck['deck_list'].strip() != str(data.get('deck_list', '')).strip():
            raise ValueError('The saved deck changed. Reopen it before changing allocations.')
        result = check_allocations(deck['deck_list'], deck_id, catalog_path, inventory_path, connection, owned)
        if index < 0 or index >= len(result['items']):
            raise ValueError('Recheck the deck before changing allocations.')
        source = next((source for source in result['items'][index]['allocation']['sources']
                       if source['deck_id'] == source_id and source['card_id'] == card_id), None)
        if source is None or quantity > source['quantity']:
            raise ValueError('Availability changed. Recheck the deck and try again.')
        current = {row['card_id']: row['quantity'] for row in connection.execute(
            'SELECT card_id, quantity FROM saved_deck_assignments WHERE deck_id=?', (deck_id,))}
        def coverage(quantities):
            return check_deck_list(deck['deck_list'], catalog_path=catalog_path, inventory_path=inventory_path,
                                   inventory_quantities=quantities)['summary']['covered_cards']
        before = coverage(current)
        current[card_id] = current.get(card_id, 0) + quantity
        if coverage(current) - before != quantity:
            raise ValueError('This deck no longer needs that many compatible copies. Recheck it first.')
        if source_id:
            old = connection.execute('SELECT quantity FROM saved_deck_assignments WHERE deck_id=? AND card_id=?', (source_id, card_id)).fetchone()['quantity']
            if old == quantity:
                connection.execute('DELETE FROM saved_deck_assignments WHERE deck_id=? AND card_id=?', (source_id, card_id))
            else:
                connection.execute('UPDATE saved_deck_assignments SET quantity=quantity-?, updated_at=CURRENT_TIMESTAMP WHERE deck_id=? AND card_id=?', (quantity, source_id, card_id))
        connection.execute('''INSERT INTO saved_deck_assignments(deck_id, card_id, quantity) VALUES(?,?,?)
            ON CONFLICT(deck_id,card_id) DO UPDATE SET quantity=quantity+excluded.quantity, updated_at=CURRENT_TIMESTAMP''',
            (deck_id, card_id, quantity))
    return {'inventory_changed': False, 'locations_changed': False}
