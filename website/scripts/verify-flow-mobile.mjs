import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
await p.goto('http://localhost:3100/', { waitUntil: 'networkidle' });
await p.evaluate(() => document.getElementById('how')?.scrollIntoView({ block: 'start' }));
await p.waitForTimeout(400);
// Walk down until the BLOCKED loop bracket is lit, capture a couple of states
let shot = 0;
const seen = new Set();
for (let i = 0; i < 40; i++) {
  await p.evaluate(() => window.scrollBy(0, 180));
  await p.waitForTimeout(140);
  const state = await p.evaluate(() => {
    const active = [...document.querySelectorAll('.fc-card')].findIndex(c => c.classList.contains('active'));
    const looping = !!document.querySelector('.fc-bracket.is-loop, .flow-canvas.is-blocked, .fc-bracket.active');
    return { active, looping };
  });
  const key = state.active + (state.looping ? 'L' : '');
  if (!seen.has(key) && state.active >= 0) {
    seen.add(key);
    await p.screenshot({ path: `.shots/flow-redo/M-${String(shot).padStart(2,'0')}-card${state.active}${state.looping?'-loop':''}.png` });
    shot++;
  }
}
await b.close();
console.log('mobile states captured:', [...seen].join(', '));
