import { chromium } from 'playwright';
const URL = process.argv[2];
const OUT = '/private/tmp/claude-501/-Users-ericdong-Desktop/ba26dd3b-d1c6-4379-a6e6-a514ce0366ee/scratchpad/mocks/live';
const b = await chromium.launch();
const errors = [];
const p = await b.newPage({ viewport: { width: 1280, height: 860 }, deviceScaleFactor: 2, colorScheme: 'dark' });
p.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
p.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
await p.goto(URL, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1000);
// go to readiness
await p.evaluate(() => document.getElementById('fr-create')?.click());
await p.waitForTimeout(600);
// inject a synthetic mixed doctor state (blocking-missing + optional-missing + ready)
const synth = {
  status: 'blocked', summary: '',
  checks: [
    { id: 'python', label: 'Embedded Python', status: 'ready', blocking: true },
    { id: 'git', label: 'Git', status: 'missing', blocking: true,
      detail: 'Git 2.30 or newer was not found on your Mac.',
      why: 'CrossAudit versions every audited result in git so nothing is silently overwritten.',
      repair: { action: 'install_git_tools', label: 'Fix automatically' } },
    { id: 'workspace', label: 'Project workspace', status: 'ready', blocking: true },
    { id: 'ssh', label: 'Remote compute client', status: 'missing', blocking: false,
      detail: 'OpenSSH client not detected.',
      why: 'Run heavier generators on a remote machine while keeping this Mac responsive.',
      repair: { action: 'open_url', label: 'Learn how', url: 'https://www.openssh.com/' } },
    { id: 'github_cli', label: 'GitHub connection tool', status: 'missing', blocking: false,
      detail: 'The GitHub CLI (gh) is not installed.',
      why: 'Back up and share your audited history with a remote you control.',
      repair: { action: 'open_url', label: 'Learn how', url: 'https://cli.github.com/' } },
  ],
};
const applied = await p.evaluate((d) => {
  if (typeof renderFirstRunReadiness === 'function') { renderFirstRunReadiness(d); return 'ok'; }
  return 'no-fn';
}, synth);
await p.waitForTimeout(400);
await p.evaluate(() => document.querySelectorAll('.fr-stage').forEach(s => { s.scrollTop = 0; }));
await p.waitForTimeout(150);
const rollup = await p.evaluate(() => document.getElementById('fr-rollup')?.textContent?.trim().slice(0, 120));
console.log('applied:', applied, '| rollup:', JSON.stringify(rollup));
await p.screenshot({ path: `${OUT}/06-readiness-attention.png` });
await b.close();
console.log('ERRORS:', errors.length ? JSON.stringify(errors) : 'none');
