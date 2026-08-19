import { chromium } from 'playwright';
const URL = process.argv[2];
const OUT = '/private/tmp/claude-501/-Users-ericdong-Desktop/ba26dd3b-d1c6-4379-a6e6-a514ce0366ee/scratchpad/mocks/live';
const b = await chromium.launch();
const errors = [];
const p = await b.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2, colorScheme: 'dark' });
p.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
p.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
await p.goto(URL, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1300);
// inject two configured providers (anthropic + openai) without touching the keychain
const info = await p.evaluate(() => {
  if (!settingsState || !settingsState.providers) return 'no-settings';
  settingsState.providers.anthropic = Object.assign({}, settingsState.providers.anthropic, { configured: true });
  settingsState.providers.openai = Object.assign({}, settingsState.providers.openai, { configured: true });
  frRoles = null;
  setFirstRunStep(4);
  return {
    genName: document.getElementById('fr-gen-name')?.textContent?.trim(),
    audName: document.getElementById('fr-aud-name')?.textContent?.trim(),
    genChips: document.getElementById('fr-gen-chips')?.textContent?.replace(/\s+/g, ' ').trim(),
    audChips: document.getElementById('fr-aud-chips')?.textContent?.replace(/\s+/g, ' ').trim(),
    genVendorOpts: [...(document.getElementById('fr-gen-vendor')?.options || [])].map(o => o.value),
    audVendorOpts: [...(document.getElementById('fr-aud-vendor')?.options || [])].map(o => o.value),
    independent: document.getElementById('fr-independent-text')?.textContent?.trim(),
    primaryDisabled: document.getElementById('fr-continue')?.disabled,
  };
});
console.log('ROLES-HAPPY:', JSON.stringify(info, null, 1));
await p.evaluate(() => document.querySelectorAll('.fr-stage').forEach(s => s.scrollTop = 0));
await p.screenshot({ path: `${OUT}/08-roles-dark.png` });

// force same-vendor to verify hard refusal
const same = await p.evaluate(() => {
  if (!frRoles) return 'no-roles';
  frRoles.gen.vendor = frRoles.aud.vendor;
  frUpdateIndependence();
  return {
    banner: document.getElementById('fr-independent-text')?.textContent?.trim(),
    msg: document.getElementById('fr-role-msg')?.textContent?.trim(),
    primaryDisabled: document.getElementById('fr-continue')?.disabled,
    bannerBad: document.getElementById('fr-independent')?.className,
  };
});
console.log('SAME-VENDOR:', JSON.stringify(same));
await p.screenshot({ path: `${OUT}/08b-roles-samevendor.png` });

// ZH check
await p.evaluate(() => { const t = document.querySelector('#hub-locale,#fr-locale,[data-locale]'); if (t) t.click(); });
await p.waitForTimeout(400);
await p.evaluate(() => { frRoles = null; setFirstRunStep(4); document.querySelectorAll('.fr-stage').forEach(s => s.scrollTop = 0); });
await p.waitForTimeout(400);
await p.screenshot({ path: `${OUT}/08c-roles-zh.png` });

await b.close();
console.log('ERRORS:', errors.length ? JSON.stringify(errors) : 'none');
