import { chromium } from 'playwright';
const URL = process.argv[2];
const OUT = '/private/tmp/claude-501/-Users-ericdong-Desktop/ba26dd3b-d1c6-4379-a6e6-a514ce0366ee/scratchpad/mocks/live';
const b = await chromium.launch();
const errors = [];
const p = await b.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2, colorScheme: 'dark' });
p.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
p.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
await p.goto(URL, { waitUntil: 'networkidle', timeout: 30000 });
await p.waitForTimeout(2500);
const info = await p.evaluate(() => {
  const banner = document.getElementById('sample-banner');
  const bodyText = document.body.innerText;
  return {
    bannerExists: !!banner,
    bannerVisible: banner ? (banner.offsetParent !== null && !banner.hidden) : false,
    bannerText: banner ? banner.innerText.replace(/\s+/g, ' ').trim() : null,
    bodyHasNotRealAudit: /not a real audit/i.test(bodyText),
    bodyHasSample: /sample/i.test(bodyText),
    isDemoClass: document.body.classList.contains('is-demo'),
    title: document.title,
    // scan for anything that might imply a REAL receipt/independent audit
    mentionsReceiptVerified: /receipt.*verifi|cryptographically bound|independently verified/i.test(bodyText),
  };
});
console.log('DEMO INFO:', JSON.stringify(info, null, 1));
await p.screenshot({ path: `${OUT}/demo-project.png`, fullPage: true });
// also a top-viewport shot (banner prominence)
await p.evaluate(() => window.scrollTo(0, 0));
await p.screenshot({ path: `${OUT}/demo-top.png` });
await b.close();
console.log('ERRORS:', errors.length ? JSON.stringify(errors) : 'none');
