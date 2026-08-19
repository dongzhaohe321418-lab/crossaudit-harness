import { chromium } from 'playwright';
const b = await chromium.launch();
const errors = [];
const p = await b.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2, colorScheme: 'dark' });
p.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
p.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
await p.goto(process.argv[2], { waitUntil: 'networkidle' });
await p.waitForTimeout(2000);
// make 2 more chats so the list has a few rows
for (let i = 0; i < 2; i++) { await p.evaluate(() => [...document.querySelectorAll('button')].find(x => /new chat/i.test(x.textContent))?.click()); await p.waitForTimeout(500); }
await p.waitForTimeout(400);
const row = await p.$('#task-list .task[data-chat-id]');
if (row) await row.hover();
await p.waitForTimeout(300);
// count on-row buttons (should be few now)
const rowBtns = await p.evaluate(() => {
  const r = document.querySelector('#task-list .task[data-chat-id]');
  return { onRowActs: r ? r.querySelectorAll('.task-act').length : 0, hasMore: !!(r && r.querySelector('.task-act.more')) };
});
console.log('ROW ACTIONS:', JSON.stringify(rowBtns));
// open the overflow menu
await p.evaluate(() => document.querySelector('#task-list .task[data-chat-id] .task-act.more')?.click());
await p.waitForTimeout(400);
const menu = await p.evaluate(() => {
  const m = document.querySelector('.chat-menu:not([hidden])');
  return { menuOpen: !!m, items: m ? [...m.querySelectorAll('button')].map(b => b.textContent.trim()) : [] };
});
console.log('MENU:', JSON.stringify(menu));
await p.screenshot({ path: '/private/tmp/claude-501/-Users-ericdong-Desktop/ba26dd3b-d1c6-4379-a6e6-a514ce0366ee/scratchpad/mocks/live/thread-menu.png', clip: { x: 0, y: 0, width: 560, height: 900 } });
await b.close();
console.log('ERRORS:', errors.length ? JSON.stringify(errors) : 'none');
