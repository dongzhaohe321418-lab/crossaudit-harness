import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const OUT = process.env.OUT || '.shots/flow-redo';
const TAG = process.env.TAG || 'base';
mkdirSync(OUT, { recursive: true });

const b = await chromium.launch();

async function capState(page, targetState) {
  // scroll to the chapter whose data-flow-step === targetState (0..7 clamp to 0..7)
  await page.evaluate((s) => {
    const chap = document.querySelector(`[data-flow-step="${s}"]`);
    if (chap) chap.scrollIntoView({ block: 'center' });
  }, Math.min(targetState, 7));
  await page.waitForTimeout(700);
  return page.evaluate(() => {
    const active = [...document.querySelectorAll('.fc-card')].findIndex((c) => c.classList.contains('active'));
    const exit = [...document.querySelectorAll('.fc-exit')].findIndex((c) => c.classList.contains('active'));
    return { active, exit };
  });
}

// Desktop viewports
for (const [w, h, label] of [[1440, 900, '1440'], [1280, 800, '1280'], [1024, 768, '1024']]) {
  const p = await b.newPage({ viewport: { width: w, height: h } });
  await p.goto('http://localhost:3100/', { waitUntil: 'networkidle' });
  await p.waitForTimeout(1200);
  for (const st of [0, 2, 5, 6, 7]) {
    const info = await capState(p, st);
    const sticky = await p.$('.flow-map-sticky');
    if (sticky) {
      await sticky.screenshot({ path: `${OUT}/${TAG}-${label}-s${st}-diagram.png` });
    }
    // full flow section framed
    if (label === '1440') {
      await p.screenshot({ path: `${OUT}/${TAG}-${label}-s${st}-viewport.png` });
    }
    console.log(`${label} target=${st} -> activeCard=${info.active} activeExit=${info.exit}`);
  }
  await p.close();
}

// Mobile 430
{
  const p = await b.newPage({ viewport: { width: 430, height: 932 } });
  await p.goto('http://localhost:3100/', { waitUntil: 'networkidle' });
  await p.waitForTimeout(1200);
  await p.evaluate(() => document.getElementById('how')?.scrollIntoView({ block: 'start' }));
  await p.waitForTimeout(600);
  await p.screenshot({ path: `${OUT}/${TAG}-430-how.png`, fullPage: false });
  // full section
  const sec = await p.$('#how');
  if (sec) await sec.screenshot({ path: `${OUT}/${TAG}-430-how-full.png` });
  // horizontal overflow check
  const overflow = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  console.log('430 horizontal overflow px:', overflow);
  await p.close();
}

await b.close();
console.log('done', TAG);
