import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 430, height: 932 }, deviceScaleFactor: 2 });
await p.goto('http://localhost:3100/', { waitUntil: 'networkidle' });
await p.waitForTimeout(1200);
for (let y = 0; y < 2400; y += 200) { await p.evaluate(yy => window.scrollTo(0, yy), y); await p.waitForTimeout(90); }
await p.evaluate(() => document.getElementById('thesis')?.scrollIntoView({ block: 'start' }));
await p.waitForTimeout(1200);
const overflow = await p.evaluate(() => document.documentElement.scrollWidth > innerWidth ? `${document.documentElement.scrollWidth}>${innerWidth}` : 'none');
await p.screenshot({ path: '.shots/REAL/thesis-mobile.png' });
await b.close();
console.log('horizontal overflow:', overflow);
