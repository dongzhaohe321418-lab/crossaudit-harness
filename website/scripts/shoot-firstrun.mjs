import { chromium } from 'playwright';
const URL = process.argv[2];
const OUT = '/private/tmp/claude-501/-Users-ericdong-Desktop/ba26dd3b-d1c6-4379-a6e6-a514ce0366ee/scratchpad/mocks/live';
import { mkdirSync } from 'fs';
mkdirSync(OUT, { recursive: true });
const b = await chromium.launch();
const errors = [];

async function fresh(w = 1280, h = 860, scheme = 'dark') {
  const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2, colorScheme: scheme });
  p.on('console', m => { if (m.type() === 'error') errors.push(`[${w}] ${m.text()}`); });
  p.on('pageerror', e => errors.push(`[${w}] PAGEERROR ${e.message}`));
  await p.goto(URL, { waitUntil: 'networkidle', timeout: 30000 });
  await p.waitForTimeout(700);
  return p;
}

// 1. dark welcome + gate assertion
let p = await fresh();
const mode = await p.evaluate(() => ({
  firstRun: document.body.classList.contains('first-run'),
  visibleStep: [...document.querySelectorAll('[data-fr-step]')].filter(s => s.offsetParent !== null).map(s => s.getAttribute('data-fr-step')),
  hasCreate: !!document.getElementById('fr-create'),
}));
console.log('GATE:', JSON.stringify(mode));
await p.screenshot({ path: `${OUT}/01-welcome-dark.png` });

// 2. advance to readiness, let doctor populate
await p.evaluate(() => document.getElementById('fr-create')?.click());
await p.waitForTimeout(3200);
const ready = await p.evaluate(() => {
  const step = [...document.querySelectorAll('[data-fr-step]')].filter(s => s.offsetParent !== null).map(s => s.getAttribute('data-fr-step'));
  const rollup = document.getElementById('fr-rollup')?.textContent?.trim().slice(0, 120);
  const groups = document.getElementById('fr-groups')?.textContent?.trim().slice(0, 200);
  return { step, rollup, groups };
});
console.log('READINESS:', JSON.stringify(ready));
await p.evaluate(() => document.querySelectorAll('.fr-stage').forEach(s => { s.scrollTop = 0; }));
await p.waitForTimeout(200);
await p.screenshot({ path: `${OUT}/02-readiness-dark.png` });
await p.close();

// 3. light welcome
p = await fresh();
await p.evaluate(() => document.documentElement.setAttribute('data-theme', 'light'));
await p.waitForTimeout(300);
await p.screenshot({ path: `${OUT}/03-welcome-light.png` });
await p.close();

// 4. narrow welcome
p = await fresh(760, 900);
await p.screenshot({ path: `${OUT}/04-welcome-narrow.png` });
await p.close();

// 5. ZH welcome (try to flip locale via any available control/global)
p = await fresh();
const localed = await p.evaluate(() => {
  const btn = document.querySelector('#fr-locale,#hub-locale,#locale-toggle,[data-locale]');
  if (btn) { btn.click(); return 'clicked ' + btn.id; }
  if (typeof applyLocale === 'function') { try { applyLocale('zh-CN'); return 'applyLocale'; } catch (e) {} }
  if (typeof setLocale === 'function') { try { setLocale('zh-CN'); return 'setLocale'; } catch (e) {} }
  return 'none';
});
await p.waitForTimeout(500);
console.log('LOCALE:', localed);
await p.screenshot({ path: `${OUT}/05-welcome-zh.png` });
await p.close();

await b.close();
console.log('CONSOLE_ERRORS:', errors.length ? JSON.stringify(errors, null, 1) : 'none');
console.log('DONE');
