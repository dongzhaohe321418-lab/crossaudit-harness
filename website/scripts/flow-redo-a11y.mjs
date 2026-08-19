import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
const OUT = '.shots/flow-redo';
mkdirSync(OUT, { recursive: true });
const b = await chromium.launch();

// reduced motion: graph should show whole & static
{
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
  await p.goto('http://localhost:3100/', { waitUntil: 'networkidle' });
  await p.waitForTimeout(1000);
  await p.evaluate(() => document.querySelector('.flow-map-sticky')?.scrollIntoView({ block: 'center' }));
  await p.waitForTimeout(500);
  const sticky = await p.$('.flow-map-sticky');
  await sticky.screenshot({ path: `${OUT}/v1-1440-reducedmotion.png` });
  const overflow = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  console.log('reduced-motion overflow px:', overflow);
  await p.close();
}

// prefers-contrast: more
{
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, contrast: 'more' });
  await p.goto('http://localhost:3100/', { waitUntil: 'networkidle' });
  await p.waitForTimeout(1000);
  await p.evaluate(() => { const c = document.querySelector('[data-flow-step="5"]'); if (c) c.scrollIntoView({ block: 'center' }); });
  await p.waitForTimeout(700);
  const sticky = await p.$('.flow-map-sticky');
  await sticky.screenshot({ path: `${OUT}/v1-1440-contrast-s5.png` });
  await p.close();
}
await b.close();
console.log('a11y done');
