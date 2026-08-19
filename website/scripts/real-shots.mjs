import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
await p.goto('http://localhost:3100/', { waitUntil: 'networkidle' });
// hero CSS loop is live (is-live=true); wait for it to reach a content-rich frame
await p.waitForTimeout(6500);
await p.screenshot({ path: '.shots/REAL/hero-anim.png' });
// flow: scroll into the graph so several nodes are lit
await p.evaluate(() => document.getElementById('how')?.scrollIntoView({ block: 'start' }));
await p.waitForTimeout(500);
for (let y = 0; y < 3400; y += 200) { await p.evaluate(() => window.scrollBy(0, 200)); await p.waitForTimeout(120); }
const idx = await p.evaluate(() => [...document.querySelectorAll('.fc-card')].findIndex(c => c.classList.contains('active')));
await p.waitForTimeout(400);
await p.screenshot({ path: '.shots/REAL/flow-anim.png' });
await b.close();
console.log('flow active card index at capture:', idx);
