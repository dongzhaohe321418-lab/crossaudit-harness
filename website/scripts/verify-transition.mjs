import { chromium } from 'playwright';
const URL = process.argv[2];
const VID = '/private/tmp/claude-501/-Users-ericdong-Desktop/ba26dd3b-d1c6-4379-a6e6-a514ce0366ee/scratchpad/mocks/live/vid';
import { mkdirSync } from 'fs';
mkdirSync(VID, { recursive: true });
const b = await chromium.launch();
const errors = [];
const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, colorScheme: 'dark', recordVideo: { dir: VID, size: { width: 1280, height: 800 } }, reducedMotion: 'no-preference' });
const p = await ctx.newPage();
p.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
p.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
await p.goto(URL, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1400); // welcome entrance cascade
const anim = await p.evaluate(() => {
  const s = [...document.querySelectorAll('[data-fr-step]')].find(x => !x.hidden);
  return s ? getComputedStyle(s).animationName : 'none';
});
await p.evaluate(() => document.getElementById('fr-create').click()); // → readiness
await p.waitForTimeout(1300);
await p.evaluate(() => document.getElementById('fr-back').click());     // → welcome
await p.waitForTimeout(1300);
await p.evaluate(() => document.getElementById('fr-create').click());   // → readiness again
await p.waitForTimeout(1300);
console.log('stage animationName:', anim);
console.log('ERRORS:', errors.length ? JSON.stringify(errors) : 'none');
await ctx.close(); // finalizes video
await b.close();
console.log('VIDEO_DIR:', VID);
