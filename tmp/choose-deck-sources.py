from pathlib import Path
p=Path('deck_allocations.py');s=p.read_text();s=s.replace('from deck_checker import check_deck_list','from deck_checker import check_deck_list, compatible_assignment_cards')
s=s.replace('    current, totals = {}, {}','    original_rows = [dict(row) for row in rows]\n    current, totals = {}, {}')
needle="    result['summary']['reserved_cards'] ="
pos=s.index(needle)
s=s[:pos]+'''    # Sources are alternatives, not an automatically selected borrowing plan.
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
                                        'printing': f"{card['set_code']} · {card['number']}"})
        choices.sort(key=lambda source: (source['deck_id'] != 0, source['deck_name'].casefold(), source['card_id']))
        allocation['sources'] = choices
''' +s[pos:]
p.write_text(s,encoding='utf-8')
p=Path('app.py');s=p.read_text(encoding='utf-8');a=s.index('        if assignments:\n',s.index('def saved_decks_snapshot'));b=s.index('        decks.append(deck)',a)
block=s[a:b];block=block.replace('        if assignments:\n','',1);block='\n'.join(line[4:] if line.startswith('    ') else line for line in block.split('\n'))
block+="        deck['allocation_missing'] = assigned_check['summary']['missing_cards']\n        deck['allocation_complete'] = assigned_check['summary']['complete']\n"
s=s[:a]+block+s[b:];p.write_text(s,encoding='utf-8')
