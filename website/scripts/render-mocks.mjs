import { chromium } from 'playwright';
const DIR = '/private/tmp/claude-501/-Users-ericdong-Desktop/ba26dd3b-d1c6-4379-a6e6-a514ce0366ee/scratchpad/mocks';
const OUT = '/private/tmp/claude-501/-Users-ericdong-Desktop/ba26dd3b-d1c6-4379-a6e6-a514ce0366ee/scratchpad/mocks/shots';
import { mkdirSync } from 'fs';
mkdirSync(OUT, { recursive: true });
const b = await chromium.launch();
const attitudes = ['A', 'B', 'C'];
for (const a of attitudes) {
  const p = await b.newPage({ viewport: { width: 1280, height: 860 }, deviceScaleFactor: 2 });
  await p.goto(`file://${DIR}/first-launch-${a}.html`, { waitUntil: 'networkidle' });
  await p.waitForTimeout(400);
  const n = await p.evaluate(() => document.querySelectorAll('section').length);
  // per-section screenshots (align to each section top)
  for (let i = 0; i < n; i++) {
    await p.evaluate((idx) => {
      const s = document.querySelectorAll('section')[idx];
      s.scrollIntoView({ block: 'start' });
      window.scrollBy(0, -2);
    }, i);
    await p.waitForTimeout(250);
    await p.screenshot({ path: `${OUT}/${a}-s${i + 1}.png` });
  }
  // full tall strip
  await p.evaluate(() => window.scrollTo(0, 0));
  await p.waitForTimeout(150);
  await p.screenshot({ path: `${OUT}/${a}-full.png`, fullPage: true });
  await p.close();
  console.log(`${a}: ${n} sections captured`);
}
await b.close();
console.log('DONE');
