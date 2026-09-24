from pathlib import Path
s=Path('tmp/check-collection-navigation.cjs').read_text(encoding="utf-8");s=s[:s.index('for(const width of [390,760,900,1024,1440])')]
s=s.replace('let saves=0;', 'let saves=0,moved=false;')
s=s.replace("if(p==='/decks')", "if(p==='/decks/transfer-allocation'){assert.equal(route.request().postDataJSON().source_deck_id,7);moved=true;return route.fulfill({json:{ok:true}});}\nif(p==='/decks')")
s=s.replace("name:'Card A',", "name:'Card A',missing:0,allocation:{index:0,assigned:moved?1:0,available:moved?1:0,reserved:moved?0:1,sources:moved?[]:Array.from({length:7},(_,i)=>({deck_id:i+2,deck_name:'Source '+(i+2),card_id:'card',quantity:1,allocated_quantity:4}))},")
s+='''for(const width of [390,1440]) {
moved=false;const {page,errors}=await setup(width);let accept=false;
page.on('dialog',async d=>{assert(d.message().includes('Source 7'));await(accept?d.accept():d.dismiss());});
await page.goto('http://fixture.test/inventory');
if(width===390)await page.locator('#mobile_tools_toggle').click();
await page.locator('#collection_decks_toggle').click();await page.locator('[data-deck-id="1"]').click();
await page.getByRole('button',{name:/Card A: 0\/1.*Review allocations/}).click();
assert.equal(await page.locator('.collection-allocation-dialog .deck-allocation-source').count(),7);
assert((await page.locator('.collection-allocation-dialog').textContent()).includes('4 allocated here'));
await page.getByRole('button',{name:'Take from Source 7',exact:true}).click();assert(!moved);
accept=true;await page.getByRole('button',{name:'Take from Source 7',exact:true}).click();
await page.getByText('1× Card A allocated to Alpha.',{exact:true}).waitFor();
assert(moved);await page.getByRole('button',{name:'Close allocations',exact:true}).click();
assert((await page.locator('.deck-view-card-status').first().textContent()).includes('1/1 allocated'));
assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
const states=await page.evaluate(()=>[allocationBadge({requested:4,missing:0,allocation:{assigned:4,available:4,reserved:0}}).tone,allocationBadge({requested:4,missing:0,allocation:{assigned:2,available:4,reserved:0}}).tone,allocationBadge({requested:4,missing:0,allocation:{assigned:2,available:2,reserved:2}}).tone,allocationBadge({requested:4,missing:2,allocation:{assigned:2,available:2,reserved:0}}).tone,allocationBadge({requested:4,missing:1,allocation:{assigned:2,available:2,reserved:1}}).tone]);
assert.deepEqual(states,['ready','available','reserved','missing','mixed']);assert.deepEqual(errors,[]);
await page.screenshot({path:`tmp/compact-badges-${width}.png`,fullPage:true});await page.close();console.log(width+': five badge states, seven donors, cancel and selected transfer passed');
}await browser.close();})().catch(e=>{console.error(e);process.exit(1)});
'''
Path('tmp/check-compact-badges.cjs').write_text(s,encoding="utf-8")

