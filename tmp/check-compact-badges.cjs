const {chromium}=require('C:/Users/erica/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
const browser=await chromium.launch({channel:'msedge',headless:true});
let decks=[{id:1,name:'Alpha',deck_list:'1 Card TST 1',card_count:1,unique_entries:1,display_image:'http://fixture.test/card-b.svg'},{id:2,name:'Beta',deck_list:'1 Card TST 1',card_count:1,unique_entries:1}];let saves=0,moved=false;
async function setup(width){const page=await browser.newPage({viewport:{width,height:740}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',async route=>{const p=new URL(route.request().url()).pathname;
if(p==='/decks/transfer-allocation'){assert.equal(route.request().postDataJSON().source_deck_id,7);moved=true;return route.fulfill({json:{ok:true}});}
if(p==='/decks')return route.fulfill({json:{ok:true,decks}});
if(p==='/decks/order'){const ids=route.request().postDataJSON().ids;decks.forEach(d=>d.sort_position=ids.indexOf(d.id));return route.fulfill({json:{ok:true}});}
if(p==='/decks/save'){const data=route.request().postDataJSON();assert(data.display_image);saves++;const deck={...data,id:3,card_count:2,unique_entries:2};decks.push(deck);return route.fulfill({json:{ok:true,deck}});}
if(p==='/inventory/cards')return route.fulfill({json:{ok:true,items:[],locations:[]}});
if(p==='/deck/check')return route.fulfill({json:{ok:true,items:[{name:'Card A',missing:0,allocation:{index:0,assigned:moved?1:0,available:moved?1:0,reserved:moved?0:1,sources:moved?[]:Array.from({length:7},(_,i)=>({deck_id:i+2,deck_name:'Source '+(i+2),card_id:'card',quantity:1,allocated_quantity:4}))},image_url:'http://fixture.test/card-a.svg',requested:1,status:'ready',deck_section:'pokemon',category:'Pokémon',set_code:'TST',number:'1',fills:[]},{name:'Card B',image_url:'http://fixture.test/card-b.svg',requested:1,status:'ready',deck_section:'trainer',category:'Trainer',set_code:'TST',number:'2',fills:[]}],ignored_basic_energy:[],errors:[],summary:{missing_cards:0,covered_cards:2,deck_cards:2,unique_lines:2}}});
if(p.endsWith('.svg'))return route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="140"><rect width="100" height="140" fill="teal"/></svg>'});
if(p==='/desktop-session.js')return route.fulfill({body:''});
const file=path.join(process.cwd(),'web',p==='/inventory'?'inventory.html':p==='/deck'?'deck.html':p.slice(1));if(!fs.existsSync(file))return route.fulfill({status:404,body:''});return route.fulfill({path:file,contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});
});return {page,errors};}
for(const width of [390,1440]) {
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
