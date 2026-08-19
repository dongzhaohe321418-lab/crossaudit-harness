import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1.5 });
await p.goto('http://localhost:3100/', { waitUntil: 'networkidle' });
await p.waitForTimeout(1500);
await p.evaluate(() => document.getElementById('how')?.scrollIntoView({ block: 'start' }));
await p.waitForTimeout(800);
// walk down through the flow slowly, capture at each auditState change
let last = -1; const shots = [];
for (let i = 0; i < 45; i++) {
  await p.evaluate(() => window.scrollBy(0, 90));
  await p.waitForTimeout(120);
  const st = await p.evaluate(() => {
    const cards = [...document.querySelectorAll('.fc-card')].findIndex(c => c.classList.contains('active'));
    const exit = [...document.querySelectorAll('.fc-exit')].findIndex(c => c.classList.contains('active'));
    return { cards, exit };
  });
  const key = `${st.cards}|${st.exit}`;
  if (key !== last && (st.cards >= 0 || st.exit >= 0)) {
    last = key;
    const name = st.exit >= 0 ? `exit${st.exit}` : `card${st.cards}`;
    if (!shots.includes(name)) { shots.push(name); await p.screenshot({ path: `.shots/flow-redo/CHK-${name}.png` }); }
  }
}
await b.close();
console.log('captured states:', shots.join(', '));
