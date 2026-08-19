import { chromium } from 'playwright';
const URL = process.argv[2];
const OUT = '/private/tmp/claude-501/-Users-ericdong-Desktop/ba26dd3b-d1c6-4379-a6e6-a514ce0366ee/scratchpad/mocks/live';
const b = await chromium.launch();
const errors = [];
const p = await b.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2, colorScheme: 'dark' });
p.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
p.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
await p.goto(URL, { waitUntil: 'networkidle', timeout: 30000 });
await p.waitForTimeout(2000);
// create two extra chats via the New chat button
for (let i = 0; i < 2; i++) {
  await p.evaluate(() => document.getElementById('new-chat-btn')?.click() || [...document.querySelectorAll('button')].find(b => /new chat/i.test(b.textContent))?.click());
  await p.waitForTimeout(600);
  // type + send nothing; just leaving new-chat mode is fine — instead create via api if button flow needs input
}
await p.waitForTimeout(500);
// Count chat rows + reveal actions by hovering the first row
const before = await p.evaluate(() => ({
  activeRows: document.querySelectorAll('#task-list .task[data-chat-id]').length,
  actionBtns: document.querySelectorAll('#task-list .task[data-chat-id] .task-act, #task-list .task[data-chat-id] [data-rename-chat],#task-list .task[data-chat-id] [data-archive-chat],#task-list .task[data-chat-id] [data-duplicate-chat],#task-list .task[data-chat-id] [data-pin-chat],#task-list .task[data-chat-id] [data-delete-chat]').length,
  hasArchivedToggle: !!document.querySelector('[data-archived-toggle]'),
}));
console.log('BEFORE:', JSON.stringify(before));
const firstRow = await p.$('#task-list .task[data-chat-id]');
if (firstRow) await firstRow.hover();
await p.waitForTimeout(400);
await p.screenshot({ path: `${OUT}/thread-row-hover.png`, clip: { x: 0, y: 0, width: 420, height: 900 } });

// archive the first chat via its archive control, then screenshot the Archived section
const archived = await p.evaluate(async () => {
  const btn = document.querySelector('#task-list .task[data-chat-id] [data-archive-chat]');
  if (!btn) return 'no-archive-btn';
  btn.click();
  return 'clicked';
});
await p.waitForTimeout(900);
// expand Archived if collapsed
await p.evaluate(() => { const t = document.querySelector('[data-archived-toggle]'); if (t && t.getAttribute('aria-expanded') !== 'true') t.click(); });
await p.waitForTimeout(400);
const after = await p.evaluate(() => ({
  archiveResult: true,
  archivedRows: document.querySelectorAll('#archived-list .task').length,
  archivedCount: document.querySelector('.archived-count')?.textContent?.trim(),
  activeRows: document.querySelectorAll('#task-list .task[data-chat-id]').length,
}));
console.log('AFTER ARCHIVE:', JSON.stringify(after), '| archive click:', archived);
await p.screenshot({ path: `${OUT}/thread-archived.png`, clip: { x: 0, y: 0, width: 420, height: 900 } });
await b.close();
console.log('ERRORS:', errors.length ? JSON.stringify(errors) : 'none');
