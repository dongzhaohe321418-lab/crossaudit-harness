import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://localhost:3100/', { waitUntil: 'networkidle' });
await p.waitForTimeout(2000);
const seq = [];
for (let y = 0; y < 9200; y += 120) {
  await p.evaluate(yy => window.scrollTo(0, yy), y);
  await p.waitForTimeout(90);
  const idx = await p.evaluate(() => [...document.querySelectorAll('.fc-card')].findIndex(c => c.classList.contains('active')));
  if (seq.length === 0 || seq[seq.length - 1] !== idx) seq.push(idx);
}
await b.close();
console.log('flow active-card index sequence while scrolling:', JSON.stringify(seq));
console.log('flow advances with scroll:', new Set(seq).size > 1);
