import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1.5 });
await p.goto('http://localhost:3100/', { waitUntil: 'networkidle' });
await p.waitForTimeout(1500);
// scroll into the flow section, capture at 3 states as auditState advances
await p.evaluate(() => { document.getElementById('how')?.scrollIntoView({ block: 'start' }); return window.scrollY; });
await p.waitForTimeout(900);
for (const [n, extra] of [[1,0],[2,700],[3,700]]) {
  if (extra) { for (let i=0;i<extra/100;i++){await p.evaluate(()=>window.scrollBy(0,100));await p.waitForTimeout(70);} }
  await p.waitForTimeout(600);
  const st = await p.evaluate(() => [...document.querySelectorAll('.fc-card')].findIndex(c=>c.classList.contains('active')));
  await p.screenshot({ path: `.shots/REAL/flow-s${n}.png` });
  console.log(`state ${n}: active card index = ${st}`);
}
const txt = await p.evaluate(() => document.getElementById('how')?.innerText || '');
await b.close();
console.log('=== text ===\n' + txt.slice(0, 900));
