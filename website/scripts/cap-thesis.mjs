import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1.5 });
await p.goto('http://localhost:3100/', { waitUntil: 'networkidle' });
await p.waitForTimeout(1500);
// scroll slowly so thesis reveals fire
for (let y = 0; y < 1800; y += 150) { await p.evaluate(yy => window.scrollTo(0, yy), y); await p.waitForTimeout(110); }
await p.evaluate(() => document.getElementById('thesis')?.scrollIntoView({ block: 'start' }));
await p.waitForTimeout(1400);
await p.screenshot({ path: '.shots/REAL/thesis-now.png' });
// also grab the raw text content so I can see what it's trying to say
const txt = await p.evaluate(() => document.getElementById('thesis')?.innerText || 'not found');
await b.close();
console.log('=== thesis section text ===');
console.log(txt);
