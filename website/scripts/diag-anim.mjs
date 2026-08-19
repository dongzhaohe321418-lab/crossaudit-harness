import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://localhost:3100/', { waitUntil: 'networkidle' });
await p.waitForTimeout(2500);
// 1. hydration probe: pure-React language toggle
const langBefore = await p.evaluate(() => document.documentElement.lang);
const clicked = await p.evaluate(() => {
  const btn = [...document.querySelectorAll('button,a,[role="button"]')].find(e => /^\s*(中|EN|中文)\s*$/.test(e.textContent || ''));
  if (btn) { btn.click(); return (btn.textContent || '').trim(); }
  return null;
});
await p.waitForTimeout(700);
const langAfter = await p.evaluate(() => document.documentElement.lang);
// 2. hero demo-window is-live (CSS anim gate)
const heroLive = await p.evaluate(() => document.querySelector('.demo-window')?.classList.contains('is-live'));
// 3. flow auditState via real scroll
await p.evaluate(() => document.getElementById('how')?.scrollIntoView({ block: 'start' }));
await p.waitForTimeout(700);
for (let i = 0; i < 10; i++) { await p.mouse.wheel(0, 280); await p.waitForTimeout(250); }
const activeIdx = await p.evaluate(() => [...document.querySelectorAll('.fc-card')].findIndex(c => c.classList.contains('active')));
await b.close();
console.log(JSON.stringify({
  hydration_langToggle_worked: langBefore !== langAfter,
  langBefore, clicked, langAfter,
  heroWindow_isLive: heroLive,
  flow_activeCardIndex_afterScroll: activeIdx,
}, null, 0));
