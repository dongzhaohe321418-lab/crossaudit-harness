import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
const errs = [];
p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
p.on('pageerror', (e) => errs.push('PAGEERROR ' + e.message));
await p.goto('http://localhost:3100/', { waitUntil: 'networkidle' });
await p.waitForTimeout(800);
for (let y = 1500; y < 9000; y += 500) { await p.evaluate((yy) => window.scrollTo(0, yy), y); await p.waitForTimeout(120); }
await b.close();
console.log('console/page errors:', errs.length, JSON.stringify(errs.slice(0, 8)));
