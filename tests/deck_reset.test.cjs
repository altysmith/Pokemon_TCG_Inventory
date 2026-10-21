const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
let chromium;
try {
  ({chromium} = require('playwright'));
} catch {
  ({chromium} = require(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')));
}

async function main() {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  try {
    for (const width of [390, 1440]) {
      const page = await browser.newPage({viewport: {width, height: 900}});
      const saved = [];
      const requests = [];
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.pathname === '/decks') return route.fulfill({json: {ok: true, decks: saved}});
        if (url.pathname === '/deck/check') return route.fulfill({json: {
          ok: true, errors: [], ignored_basic_energy: [], clipboard_deck_list: '1 Pikachu SVI 63',
          items: [{name: 'Pikachu', category: 'Pokémon', deck_section: 'pokemon', requested: 1,
            covered: 1, missing: 0, set_code: 'SVI', number: '63', status: 'ready',
            image_url: 'https://cards.test/pikachu.png'}],
          summary: {deck_cards: 1, covered_cards: 1, missing_cards: 0, unique_lines: 1},
        }});
        if (url.pathname === '/decks/save') {
          const body = route.request().postDataJSON();
          requests.push(body);
          const deck = {id: saved.length + 1, name: body.name, deck_list: body.deck_list,
            display_image: body.display_image, card_count: 1, unique_entries: 1,
            updated_at: '2026-10-21 12:00:00'};
          saved.push(deck);
          return route.fulfill({json: {ok: true, deck}});
        }
        if (url.pathname === '/desktop-session.js') return route.fulfill({body: ''});
        if (url.hostname === 'cards.test') return route.fulfill({status: 404, body: ''});
        const file = url.pathname === '/deck' ? 'deck.html' : url.pathname.slice(1);
        const full = path.join(__dirname, '..', 'web', file);
        if (!fs.existsSync(full)) return route.fulfill({status: 404, body: ''});
        return route.fulfill({path: full, contentType: file.endsWith('.js') ? 'application/javascript'
          : file.endsWith('.css') ? 'text/css' : 'text/html'});
      });
      await page.goto('http://deck.test/deck');
      await page.locator('#deck_new').click();
      assert.equal(await page.locator('#deck_list').isVisible(), true);
      for (const name of ['First deck', 'Second deck']) {
        await page.locator('#deck_list').fill('1 Pikachu SVI 63');
        await page.locator('#deck_submit').click();
        await page.locator('#deck_save_panel').waitFor({state: 'visible'});
        assert.equal(await page.locator('#deck_list').isVisible(), true);
        await page.locator('#deck_name').fill(name);
        await page.locator('#deck_display_card').selectOption('https://cards.test/pikachu.png');
        await page.locator('#deck_save').click();
        await page.getByText(`${name} was saved. Ready to build another deck.`).waitFor();
        assert.equal(await page.locator('#deck_list').inputValue(), '');
        assert.equal(await page.locator('#deck_name').inputValue(), '');
        assert.equal(await page.locator('#deck_display_card').inputValue(), '');
        assert.equal(await page.locator('#deck_list').isVisible(), true);
        assert.equal(await page.locator('#deck_save_panel').isVisible(), false);
      }
      assert.deepEqual(requests.map(request => request.id), [0, 0]);
      assert.deepEqual(saved.map(deck => deck.name), ['First deck', 'Second deck']);
      assert.deepEqual(errors, []);
      await page.close();
      process.stdout.write(`${width}px: two saves created separate decks; editor stayed visible\n`);
    }
  } finally {
    await browser.close();
  }
}

main().catch(error => {console.error(error); process.exitCode = 1;});
