import { chromium } from 'playwright';
const URL = 'https://crossaudit-v4.vercel.app';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
const resp = await p.goto(URL, { waitUntil: 'networkidle', timeout: 45000 });
console.log('HTTP status:', resp.status());
await p.waitForTimeout(2000);

const checks = await p.evaluate(() => {
  const txt = document.body.innerText;
  return {
    title: document.title,
    hasCodex: /codex/i.test(document.documentElement.outerHTML),
    heroHeading: (document.querySelector('h1')?.innerText || '').slice(0, 80),
    navItems: [...document.querySelectorAll('nav a, header a')].map(a => a.innerText.trim()).filter(Boolean).slice(0, 8),
    hasFlowGraph: !!document.querySelector('.fc-card, [class*="flow"]'),
    hasThesis: /vendor|auditor|generator/i.test(txt),
    downloadCta: [...document.querySelectorAll('a,button')].map(e=>e.innerText.trim()).find(t=>/download/i.test(t)) || null,
    sectionCount: document.querySelectorAll('section').length,
    bodyLen: txt.length,
  };
});
console.log(JSON.stringify(checks, null, 2));

// hero screenshot
await p.screenshot({ path: '.shots/LIVE/home.png' });
// scroll to flow section and shoot
await p.evaluate(() => document.getElementById('how')?.scrollIntoView({ block: 'start' }));
await p.waitForTimeout(600);
for (let y = 0; y < 1600; y += 200) { await p.evaluate(() => window.scrollBy(0, 200)); await p.waitForTimeout(120); }
await p.screenshot({ path: '.shots/LIVE/flow.png' });

// language toggle test (find the 中/EN toggle)
const beforeLang = await p.evaluate(() => document.documentElement.lang || document.querySelector('h1')?.innerText?.slice(0,40));
await b.close();
console.log('lang/heading sample:', beforeLang);
console.log('DONE');
