import { chromium } from 'playwright';
const b = await chromium.launch();
let alertFired = false;
const p = await b.newPage();
p.on('dialog', d => { alertFired = true; d.dismiss(); });
await p.goto(process.argv[2], { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1200);
const r = await p.evaluate(() => {
  const out = {};
  for (const n of [100000, 1000000]) {
    const big = '['.repeat(n);
    const t0 = performance.now();
    renderMarkdown(big);
    out['brackets_' + n + '_ms'] = Math.round(performance.now() - t0);
  }
  // also a[a]( pattern + a real link + xss recheck
  const t1 = performance.now(); renderMarkdown('[a]('.repeat(300000)); out['ablink_ms'] = Math.round(performance.now() - t1);
  const link = renderMarkdown('[ok](https://example.com) and [bad](javascript:alert(1))').html;
  out.realLinkKept = /href="https:\/\/example\.com"/.test(link);
  out.jsLinkRejected = !/javascript:/i.test(link) || !/<a[^>]+href="javascript/i.test(link);
  const xss = renderMarkdown('<script>alert(1)</script> [x](javascript:alert(1)) <img src=x onerror=alert(1)>').html;
  const div = document.createElement('div'); div.innerHTML = xss;
  out.noScript = !div.querySelector('script'); out.noImg = !div.querySelector('img');
  out.noJsHref = ![...div.querySelectorAll('a[href]')].some(a => /^javascript:/i.test(a.getAttribute('href')));
  return out;
});
await p.waitForTimeout(200);
console.log(JSON.stringify({ alertFired, ...r }, null, 1));
await b.close();
