const {chromium}=require('C:/Users/erica/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
const browser=await chromium.launch({channel:'msedge',headless:true});
let decks=[{id:1,name:'Alpha',deck_list:'1 Card TST 1',card_count:1,unique_entries:1,display_image:'http://fixture.test/card-b.svg'},{id:2,name:'Beta',deck_list:'1 Card TST 1',card_count:1,unique_entries:1}];let saves=0;
async function setup(width){const page=await browser.newPage({viewport:{width,height:740}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',async route=>{const p=new URL(route.request().url()).pathname;
if(p==='/decks')return route.fulfill({json:{ok:true,decks}});
if(p==='/decks/order'){const ids=route.request().postDataJSON().ids;decks.forEach(d=>d.sort_position=ids.indexOf(d.id));return route.fulfill({json:{ok:true}});}
if(p==='/decks/save'){const data=route.request().postDataJSON();assert(data.display_image);saves++;const deck={...data,id:3,card_count:2,unique_entries:2};decks.push(deck);return route.fulfill({json:{ok:true,deck}});}
if(p==='/inventory/cards')return route.fulfill({json:{ok:true,items:[],locations:[]}});
if(p==='/deck/check')return route.fulfill({json:{ok:true,items:[{name:'Card A',allocation:{index:0,assigned:0,available:0,reserved:1,sources:[{deck_id:2,deck_name:'Beta',quantity:1}]},image_url:'http://fixture.test/card-a.svg',requested:1,status:'ready',deck_section:'pokemon',category:'Pokémon',set_code:'TST',number:'1',fills:[]},{name:'Card B',allocation:{index:1,assigned:1,available:1,reserved:0,sources:[]},image_url:'http://fixture.test/card-b.svg',requested:1,status:'ready',deck_section:'trainer',category:'Trainer',set_code:'TST',number:'2',fills:[]}],ignored_basic_energy:[],errors:[],summary:{missing_cards:0,covered_cards:2,deck_cards:2,unique_lines:2}}});
if(p.endsWith('.svg'))return route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="140"><rect width="100" height="140" fill="teal"/></svg>'});
if(p==='/desktop-session.js')return route.fulfill({body:''});
const file=path.join(process.cwd(),'web',p==='/inventory'?'inventory.html':p==='/deck'?'deck.html':p.slice(1));if(!fs.existsSync(file))return route.fulfill({status:404,body:''});return route.fulfill({path:file,contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});
});return {page,errors};}
for(const width of [390,1440]) {
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
