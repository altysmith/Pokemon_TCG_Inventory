from pathlib import Path
s=Path('tmp/check-collection-navigation.cjs').read_text()
s=s[:s.index('for(const width of [390,760,900,1024,1440])')]
s=s.replace("name:'Card A',", "name:'Card A',allocation:{index:0,assigned:0,available:0,reserved:1,sources:[{deck_id:2,deck_name:'Beta',quantity:1}]},")
s=s.replace("name:'Card B',", "name:'Card B',allocation:{index:1,assigned:1,available:1,reserved:0,sources:[]},")
s+='''for(const width of [390,1440]) {
const {page,errors}=await setup(width);
await page.goto('http://fixture.test/inventory');
if(width===390)await page.locator('#mobile_tools_toggle').click();
await page.locator('#collection_decks_toggle').click();
await page.locator('[data-deck-id="1"]').click();
await page.getByRole('heading',{name:'Cards needing allocation'}).waitFor();
assert.equal(await page.locator('.collection-allocation-summary a').count(),1);
assert((await page.locator('.collection-allocation-summary').textContent()).includes('In Beta'));
assert((await page.locator('.deck-view-card-status').first().textContent()).includes('allocate 1'));
await page.locator('.collection-allocation-summary a').click();
await page.locator('.deck-allocation-controls').waitFor();
assert((await page.locator('#deck_builder_preview h3').textContent()).includes('Card A'));
assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
assert.deepEqual(errors,[]);await page.close();console.log(width+': shortage quantity, source deck, card status and allocation link passed');
}
await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
'''
Path('tmp/check-collection-shortages.cjs').write_text(s)
