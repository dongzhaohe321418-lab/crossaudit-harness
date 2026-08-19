import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 });
await p.goto('http://localhost:3100/', { waitUntil: 'networkidle' });
await p.waitForTimeout(1200);
for (let i = 0; i < 12; i++) { await p.evaluate(() => window.scrollBy(0, 140)); await p.waitForTimeout(80); }
await p.evaluate(() => document.getElementById('thesis')?.scrollIntoView({ block: 'start' }));
await p.waitForTimeout(1200);
const el = await p.$('.track-crossaudit');
const box = await el.boundingBox();
// crop just the top-left region where the loop + generator/auditor live
await p.screenshot({ path: '.shots/REAL/loop-zoom.png', clip: { x: box.x, y: box.y, width: box.width * 0.6, height: box.height * 0.85 } });
await b.close();
console.log('captured loop zoom');
