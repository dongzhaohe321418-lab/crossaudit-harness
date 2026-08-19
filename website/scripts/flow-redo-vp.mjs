import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://localhost:3100/', { waitUntil: 'networkidle' });
await p.waitForTimeout(1000);
for (const st of [5, 6]) {
  await p.evaluate((s) => {
    const c = document.querySelector(`[data-flow-step="${s}"]`);
    if (c) c.scrollIntoView({ block: 'center' });
  }, st);
  await p.waitForTimeout(700);
  await p.screenshot({ path: `.shots/flow-redo/v1-1440-s${st}-viewport.png` });
}
await b.close();
console.log('vp done');
