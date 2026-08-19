import { chromium } from 'playwright';
import fs from 'fs';
const dir = '.shots/final-current';
fs.mkdirSync(dir, { recursive: true });
const ids = ['product','thesis','how','loop','workspace','audit','capabilities','science','security','download'];
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
await p.goto('http://localhost:3000/', { waitUntil: 'networkidle' });
await p.evaluate(() => document.fonts.ready);
await p.waitForTimeout(1400);
// prime: smooth pass to trip observers once
await p.evaluate(async () => { for (let y=0;y<document.body.scrollHeight;y+=350){window.scrollTo(0,y);await new Promise(r=>setTimeout(r,180));} });
for (let i=0;i<ids.length;i++){
  await p.evaluate(id => document.getElementById(id)?.scrollIntoView({block:'start',behavior:'instant'}), ids[i]);
  await p.waitForTimeout(1300);
  if (ids[i]==='product') await p.waitForTimeout(2200); // hero loop -> delivered
  await p.screenshot({ path: `${dir}/s-${String(i+1).padStart(2,'0')}-${ids[i]}.png` });
}
const m = await b.newPage({ viewport: { width: 430, height: 932 }, deviceScaleFactor: 2 });
await m.goto('http://localhost:3000/', { waitUntil: 'networkidle' });
await m.waitForTimeout(2500);
await m.screenshot({ path: `${dir}/s-mobile.png` });
await b.close(); console.log('done');
