import { chromium } from 'playwright';
const URL = process.argv[2];
const OUT = '/private/tmp/claude-501/-Users-ericdong-Desktop/ba26dd3b-d1c6-4379-a6e6-a514ce0366ee/scratchpad/mocks/live';
const b = await chromium.launch();
const errors = [];
const p = await b.newPage({ viewport: { width: 1280, height: 860 }, deviceScaleFactor: 2, colorScheme: 'dark' });
p.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
p.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
await p.goto(URL, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1200);
await p.evaluate(() => document.getElementById('fr-create')?.click());
await p.waitForTimeout(3200);
await p.evaluate(() => document.querySelectorAll('.fr-stage').forEach(s => s.scrollTop = 0));
const allReady = await p.evaluate(() => {
  const d = document.querySelector('.fr-ready-group');
  return {
    hasReadyDetails: !!d,
    open: d ? d.open : null,
    summary: d ? d.querySelector('summary')?.textContent?.replace(/\s+/g, ' ').trim() : null,
    rollup: document.getElementById('fr-rollup')?.textContent?.trim(),
    rowsVisibleWhenClosed: d ? d.querySelector('.fr-rows')?.offsetHeight : null,
  };
});
console.log('ALL-READY:', JSON.stringify(allReady));
await p.screenshot({ path: `${OUT}/02b-readiness-collapsed.png` });
// expand
await p.evaluate(() => document.querySelector('.fr-ready-group > summary')?.click());
await p.waitForTimeout(300);
const expanded = await p.evaluate(() => {
  const d = document.querySelector('.fr-ready-group');
  return { open: d?.open, rowsHeight: d?.querySelector('.fr-rows')?.offsetHeight };
});
console.log('EXPANDED:', JSON.stringify(expanded));
await p.evaluate(() => document.querySelectorAll('.fr-stage').forEach(s => s.scrollTop = 0));
await p.screenshot({ path: `${OUT}/02c-readiness-expanded.png` });

// inject attention state
await p.evaluate(() => {
  renderFirstRunReadiness({
    status: 'blocked', checks: [
      { id: 'python', label: 'Embedded Python', status: 'ready', blocking: true },
      { id: 'workspace', label: 'Project workspace', status: 'ready', blocking: true },
      { id: 'macos', label: 'macOS', status: 'ready', blocking: true },
      { id: 'git', label: 'Git', status: 'missing', blocking: true, why: 'CrossAudit versions every audited result in git so nothing is silently overwritten.', repair: { action: 'install_git_tools', label: 'Fix automatically' } },
      { id: 'ssh', label: 'Remote compute client', status: 'missing', blocking: false, why: 'Run heavier generators on a remote machine while keeping this Mac responsive.', repair: { action: 'open_url', label: 'Learn how', url: 'https://x' } },
    ],
  });
  document.querySelectorAll('.fr-stage').forEach(s => s.scrollTop = 0);
});
await p.waitForTimeout(300);
const attn = await p.evaluate(() => ({
  rollup: document.getElementById('fr-rollup')?.textContent?.trim(),
  readySummary: document.querySelector('.fr-ready-group summary')?.textContent?.replace(/\s+/g, ' ').trim(),
  readyOpen: document.querySelector('.fr-ready-group')?.open,
  attnVisible: !!document.querySelector('.fr-group .fr-fix, [data-fr-fix]'),
}));
console.log('ATTENTION:', JSON.stringify(attn));
await p.screenshot({ path: `${OUT}/06b-readiness-attention-collapsed.png` });

// ZH check on the collapsed summary
await p.evaluate(() => { const t = document.querySelector('#hub-locale'); if (t) t.click(); });
await p.waitForTimeout(500);
const zh = await p.evaluate(() => document.querySelector('.fr-ready-group summary')?.textContent?.replace(/\s+/g, ' ').trim());
console.log('ZH-SUMMARY:', JSON.stringify(zh));
await b.close();
console.log('ERRORS:', errors.length ? JSON.stringify(errors) : 'none');
