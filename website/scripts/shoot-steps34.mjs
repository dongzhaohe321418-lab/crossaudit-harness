import { chromium } from 'playwright';
const URL = process.argv[2];
const OUT = '/private/tmp/claude-501/-Users-ericdong-Desktop/ba26dd3b-d1c6-4379-a6e6-a514ce0366ee/scratchpad/mocks/live';
const b = await chromium.launch();
const errors = [];
const p = await b.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2, colorScheme: 'dark' });
p.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
p.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
await p.goto(URL, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1200);

// --- click-through to confirm Continue wiring: step1 -> 2 -> 3 ---
await p.evaluate(() => document.getElementById('fr-create')?.click());
await p.waitForTimeout(800);
await p.evaluate(() => document.getElementById('fr-continue')?.click()); // 2 -> 3
await p.waitForTimeout(1400);
let step = await p.evaluate(() => [...document.querySelectorAll('[data-fr-step]')].filter(s => !s.hidden).map(s => s.getAttribute('data-fr-step')));
const prov = await p.evaluate(() => {
  const rows = [...document.querySelectorAll('.fr-prov, [class*="fr-prov"]')];
  const keys = [...document.querySelectorAll('input[id^="fr-key-"]')];
  return {
    step: [...document.querySelectorAll('[data-fr-step]')].filter(s => !s.hidden).map(s => s.getAttribute('data-fr-step')),
    keyInputs: keys.length,
    allPassword: keys.every(k => k.type === 'password'),
    hasChatGPT: !!document.getElementById('fr-chatgpt'),
    firstKeyId: keys[0]?.id,
  };
});
console.log('STEP3:', JSON.stringify(prov));
await p.evaluate(() => document.querySelectorAll('.fr-stage').forEach(s => s.scrollTop = 0));
await p.screenshot({ path: `${OUT}/07-providers-dark.png` });

// --- reveal-only-typed test ---
const revealTest = await p.evaluate(() => {
  const k = document.querySelector('input[id^="fr-key-"]');
  if (!k) return 'no-key-input';
  k.value = 'sk-TESTVALUE-123';
  k.dispatchEvent(new Event('input', { bubbles: true }));
  // find a reveal control near this row
  const row = k.closest('.fr-prov,[class*="fr-prov"],div');
  const reveal = row && [...row.querySelectorAll('button,[role=button]')].find(x => /reveal|show|eye/i.test(x.title + x.textContent + x.className + (x.getAttribute('aria-label') || '')));
  const before = k.type;
  if (reveal) reveal.click();
  const after = k.type;
  return { before, after, valueVisible: k.type === 'text' && k.value.includes('TESTVALUE') };
});
console.log('REVEAL:', JSON.stringify(revealTest));

// --- step 4 roles ---
await p.evaluate(() => (typeof setFirstRunStep === 'function') && setFirstRunStep(4));
await p.waitForTimeout(1400);
const roles = await p.evaluate(() => {
  const gv = document.getElementById('fr-gen-vendor'), av = document.getElementById('fr-aud-vendor');
  const opts = s => s ? [...s.options].map(o => o.value) : null;
  return {
    step: [...document.querySelectorAll('[data-fr-step]')].filter(s => !s.hidden).map(s => s.getAttribute('data-fr-step')),
    genName: document.getElementById('fr-gen-name')?.textContent?.trim(),
    audName: document.getElementById('fr-aud-name')?.textContent?.trim(),
    genChips: document.getElementById('fr-gen-chips')?.textContent?.trim().slice(0, 120),
    genVendorOpts: opts(gv), audVendorOpts: opts(av),
    independent: document.getElementById('fr-independent-text')?.textContent?.trim(),
  };
});
console.log('STEP4:', JSON.stringify(roles));
await p.evaluate(() => document.querySelectorAll('.fr-stage').forEach(s => s.scrollTop = 0));
await p.screenshot({ path: `${OUT}/08-roles-dark.png` });

// --- same-vendor refusal test ---
const sameVendor = await p.evaluate(() => {
  const gv = document.getElementById('fr-gen-vendor'), av = document.getElementById('fr-aud-vendor');
  if (!gv || !av) return 'no-selects';
  // force both to the auditor's vendor
  const target = av.value;
  gv.value = target; gv.dispatchEvent(new Event('change', { bubbles: true }));
  const msg = document.getElementById('fr-role-msg')?.textContent?.trim();
  const primary = document.getElementById('fr-continue');
  return { forced: target, msg, primaryDisabled: primary ? primary.disabled : 'no-primary' };
});
console.log('SAME_VENDOR:', JSON.stringify(sameVendor));
await p.screenshot({ path: `${OUT}/08b-roles-samevendor.png` });

await b.close();
console.log('ERRORS:', errors.length ? JSON.stringify(errors) : 'none');
