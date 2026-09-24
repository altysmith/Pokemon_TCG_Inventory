const {chromium}=require('C:/Users/erica/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const root=process.cwd();
const decks=['Raging Bolt ex','Charizard ex','Gardevoir ex','Dragapult ex','Ceruledge ex','A very long deck name for testing desktop wrapping'].map((name,i)=>({id:i+1,name,card_count:60,unique_entries:18,deck_list:`4 ${name} TST ${i+1}`,updated_at:'2026-09-18 12:00:00'}));
const result={ok:true,errors:[],items:[{name:"Raging Bolt ex",category:"Pokémon",deck_section:"pokemon",requested:4,covered:2,missing:2,set_code:"TEF",number:"123",status:"missing"},{name:"Professor Research",category:"Trainer",deck_section:"trainer",requested:4,covered:4,missing:0,set_code:"SVI",number:"189",status:"ready"}],ignored_basic_energy:[],summary:{missing_cards:2,deck_cards:60,covered_cards:58,unique_lines:18}};
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const errors=[];
 async function pageFor(width,before=false){
 const page=await browser.newPage({viewport:{width,height:1000},reducedMotion:'reduce'});
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',async route=>{
 const p=new URL(route.request().url()).pathname;
 if(p==='/decks')return route.fulfill({json:{ok:true,decks}});
 if(p==='/deck/check')return route.fulfill({json:result});
 if(p==='/desktop-session.js')return route.fulfill({body:''});
 const file=p==='/deck'?'deck.html':p.slice(1);
 const base=before && ['deck.html','deck.js','style.css'].includes(file)?'tmp/deck-desktop-before':'web';
 const full=path.join(root,base,file);
 if(!fs.existsSync(full))return route.fulfill({status:404,body:''});
 await route.fulfill({path:full,contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});
 });
 await page.goto('http://deck.test/deck');
 await page.locator('.has-deck-preview').last().waitFor();
 await page.evaluate(()=>document.fonts.ready); await page.addStyleTag({content:'html {scroll-behavior:auto !important}'});
 return page;
 }
 for(const width of [390,760]){
 const old=await pageFor(width,true),page=await pageFor(width);
 const a=await old.screenshot({fullPage:true}),b=await page.screenshot({fullPage:true});
 assert(a.equals(b),`mobile gallery differs at ${width}`);
 await old.locator('[data-open-deck="1"]').click();await page.locator('[data-open-deck="1"]').click();
 await old.locator('#deck_summary').waitFor();await page.locator('#deck_summary').waitFor();
 await old.waitForTimeout(650); await page.waitForTimeout(650); await old.evaluate(()=>window.scrollTo({top:0,behavior:"instant"}));await page.evaluate(()=>window.scrollTo({top:0,behavior:"instant"}));
 assert((await old.screenshot({path:"tmp/mobile-old.png",fullPage:true})).equals(await page.screenshot({path:"tmp/mobile-new.png",fullPage:true})),`mobile detail differs at ${width}`);
 await old.close();await page.close();
 console.log(`Mobile ${width}: gallery and detail pixel-identical`);
 }
 for(const width of [761,1024,1440,1920]){
 const page=await pageFor(width);
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) console.log(await page.evaluate(()=>[...document.querySelectorAll("body *")].filter(e=>e.getBoundingClientRect().right>innerWidth).map(e=>[e.tagName,e.className,e.getBoundingClientRect().right]))); assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`gallery overflow ${width}`);
 if(width===1440) await page.screenshot({path:'tmp/deck-desktop-gallery.png',fullPage:true});
 await page.locator('[data-open-deck="1"]').click();await page.locator('#deck_summary').waitFor();
 assert(!(await page.locator('.deck-library-panel').isVisible()));
 assert(!(await page.locator('#deck_import_panel').isVisible()));
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`detail overflow ${width}`);
 await page.locator('#deck_edit_current').click();assert(await page.locator('#deck_list').isVisible());
 await page.locator('#deck_back').click();assert(await page.locator('.deck-library-panel').isVisible());
 await page.locator('#deck_new').click();assert(await page.locator('#deck_list').isVisible());
 await page.locator('#deck_back').click();
 await page.locator('.deck-library-card').filter({has:page.locator('[data-open-deck="1"]')}).locator('summary').click();assert(await page.locator('[data-edit-deck="1"]').isVisible());
 await page.locator('[data-edit-deck="1"]').click();assert.equal(await page.locator('#deck_list').inputValue(),decks[0].deck_list);
 await page.close();console.log(`Desktop ${width}: gallery/detail/edit/back/new pass; no overflow`);
 }
 assert.deepEqual(errors,[]);await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});




