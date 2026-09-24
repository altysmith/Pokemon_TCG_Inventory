const {chromium}=require('C:/Users/erica/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
const browser=await chromium.launch({channel:'msedge',headless:true});
for(const width of [390,761,1440]){
const page=await browser.newPage({viewport:{width,height:1000}});let moved=false,writes=0,accept=false;const errors=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('dialog',async d=>{assert(d.message().includes('Gardevoir'));await (accept?d.accept():d.dismiss());});
await page.route('**/*',async route=>{
const p=new URL(route.request().url()).pathname;
if(p==='/decks')return route.fulfill({json:{ok:true,decks:[{id:1,name:'Dragapult',deck_list:'1 Unfair Stamp TWM 165',card_count:1,unique_entries:1}]}});
if(p==='/decks/transfer-allocation'){
 const data=route.request().postDataJSON();assert.equal(data.id,1);assert.equal(data.source_deck_id,2);assert.equal(data.quantity,1);assert.equal(data.card_id,'stamp');writes++;moved=true;return route.fulfill({json:{ok:true}});
}
if(p==='/deck/check')return route.fulfill({json:{ok:true,errors:[],items:[{name:'Unfair Stamp',category:'Trainer',deck_section:'trainer',requested:1,covered:1,missing:0,status:'ready',set_code:'TWM',number:'165',fills:[],allocation:{index:0,assigned:moved?1:0,reserved:moved?0:1,available:moved?1:0,editable:true,sources:moved?[]:[{deck_id:2,deck_name:'Gardevoir',card_id:'stamp',quantity:1}]}}],ignored_basic_energy:[],summary:{missing_cards:0,deck_cards:1,covered_cards:1,unique_lines:1,reserved_cards:moved?0:1}}});
if(p==='/desktop-session.js')return route.fulfill({body:''});
const file=path.join(process.cwd(),'web',p==='/deck'?'deck.html':p.slice(1));
if(!fs.existsSync(file))return route.fulfill({status:404,body:''});
return route.fulfill({path:file,contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});
});
await page.goto('http://allocation.test/deck');await page.locator('[data-open-deck="1"]').click();
await page.getByText('Buildable by moving 1 card.',{exact:true}).waitFor();
assert.equal(writes,0);
await page.locator('[data-allocation-source="0"]').click();assert.equal(writes,0);
accept=true;await page.locator('[data-allocation-source="0"]').click();
await page.getByText('You can build this deck.',{exact:true}).waitFor();
if(width>760) assert(!(await page.locator('#deck_import_panel').isVisible()),'editor unexpectedly visible'); assert.equal(writes,1);assert(await page.getByText('1 assigned to this deck · 1 available of 1 needed',{exact:true}).isVisible());
assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
assert.deepEqual(errors,[]);
await page.screenshot({path:`tmp/allocation-${width}.png`,fullPage:true});await page.close();console.log(`${width}: warning, cancel, transfer, refreshed status, no overflow/errors`);
}
await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});

