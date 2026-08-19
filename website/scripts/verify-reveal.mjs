import { chromium } from 'playwright';
import fs from 'fs';
const dir = '.shots/DELIVER'; fs.mkdirSync(dir, { recursive: true });
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
await p.goto('http://localhost:3000/', { waitUntil: 'networkidle' });
await p.waitForTimeout(2000);
// real scroll through the whole page to trip reveals
for (let i = 0; i < 20; i++) { await p.mouse.wheel(0, 650); await p.waitForTimeout(160); }
await p.waitForTimeout(600);
const total = await p.$$eval('[data-reveal]', e => e.length);
const vis = await p.$$eval('[data-reveal]', e => e.filter(x => x.classList.contains('is-visible')).length);
const sy = await p.evaluate(() => window.scrollY || document.scrollingElement.scrollTop);
console.log('VINEXT 3000:', JSON.stringify({ total, visible: vis, scrollY: Math.round(sy) }));
// capture each section (now revealed)
const ids = ['product','thesis','how','loop','workspace','audit','capabilities','science','security','download'];
for (const id of ids) {
  await p.evaluate(x => document.getElementById(x)?.scrollIntoView({ block: 'start' }), id);
  await p.waitForTimeout(700);
  if (id === 'product') await p.waitForTimeout(2200);
  await p.screenshot({ path: `${dir}/${id}.png` });
}
const m = await b.newPage({ viewport: { width: 430, height: 932 }, deviceScaleFactor: 2 });
await m.goto('http://localhost:3000/', { waitUntil: 'networkidle' });
await m.waitForTimeout(1500);
for (let i = 0; i < 6; i++) { await m.mouse.wheel(0, 500); await m.waitForTimeout(150); }
await m.evaluate(() => window.scrollTo(0,0)); await m.waitForTimeout(1200);
await m.screenshot({ path: `${dir}/mobile.png`, fullPage: false });
await b.close();
console.log('shots done');
