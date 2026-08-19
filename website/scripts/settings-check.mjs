import { chromium } from 'playwright';
const b = await chromium.launch();
const errors = [];
const p = await b.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2, colorScheme: 'dark' });
p.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
p.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
await p.goto(process.argv[2], { waitUntil: 'networkidle' });
await p.waitForTimeout(2000);
// open settings
await p.evaluate(() => (typeof openSettings === 'function') ? openSettings() : document.getElementById('settings-open')?.click());
await p.waitForTimeout(800);
const nav = await p.evaluate(() => {
  const btns = [...document.querySelectorAll('.settings-nav .settings-nav-button')];
  return {
    groupCount: btns.length,
    groups: btns.map(x => (x.querySelector('b')?.textContent || x.textContent).trim()),
    hasSearch: !!document.getElementById('settings-search'),
  };
});
console.log('NAV:', JSON.stringify(nav));
await p.screenshot({ path: '/private/tmp/claude-501/-Users-ericdong-Desktop/ba26dd3b-d1c6-4379-a6e6-a514ce0366ee/scratchpad/mocks/live/settings-general.png' });
// click a thin group — Agent behavior — check honest note (no fake toggles)
await p.evaluate(() => { const btns=[...document.querySelectorAll('.settings-nav .settings-nav-button')]; const t=btns.find(x=>/agent/i.test(x.textContent)); t&&t.click(); });
await p.waitForTimeout(400);
const thin = await p.evaluate(() => {
  const pane = document.querySelector('[data-settings-pane]:not([hidden])');
  return { text: pane ? pane.innerText.replace(/\s+/g,' ').trim().slice(0,300) : null,
           realInputs: pane ? pane.querySelectorAll('input:not([type=hidden]),select,textarea').length : 0 };
});
console.log('AGENT-PANE:', JSON.stringify(thin));
await p.screenshot({ path: '/private/tmp/claude-501/-Users-ericdong-Desktop/ba26dd3b-d1c6-4379-a6e6-a514ce0366ee/scratchpad/mocks/live/settings-thin.png' });
// search
await p.evaluate(() => { const s=document.getElementById('settings-search'); if(s){ s.value='keychain'; s.dispatchEvent(new Event('input',{bubbles:true})); } });
await p.waitForTimeout(400);
const search = await p.evaluate(() => {
  const res = document.getElementById('settings-search-results');
  return { resultsVisible: res && res.offsetParent !== null, items: res ? [...res.querySelectorAll('button,[role=option]')].map(x=>x.textContent.replace(/\s+/g,' ').trim()).slice(0,6) : [] };
});
console.log('SEARCH(keychain):', JSON.stringify(search));
await p.screenshot({ path: '/private/tmp/claude-501/-Users-ericdong-Desktop/ba26dd3b-d1c6-4379-a6e6-a514ce0366ee/scratchpad/mocks/live/settings-search.png' });
await b.close();
console.log('ERRORS:', errors.length ? JSON.stringify(errors) : 'none');
