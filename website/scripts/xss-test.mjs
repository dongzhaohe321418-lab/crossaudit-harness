import { chromium } from 'playwright';
const b = await chromium.launch();
let alertFired = false;
const p = await b.newPage();
p.on('dialog', d => { alertFired = true; d.dismiss(); });   // any alert() = XSS
await p.goto(process.argv[2], { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1500);
const payloads = [
  '<script>window.__xss=1;alert(1)</script>',
  '[click](javascript:alert(1))',
  '[click](JaVaScRiPt:alert(1))',
  '[click](java\tscript:alert(1))',
  '[click](  javascript:alert(1))',
  '[click](&#106;avascript:alert(1))',
  '[click](data:text/html,<script>alert(1)</script>)',
  '[click](vbscript:msgbox(1))',
  '<img src=x onerror="window.__xss=1;alert(1)">',
  '<svg onload="alert(1)">',
  '![alt](x" onerror="alert(1))',
  '`<script>alert(1)</script>`',
  '<a href="javascript:alert(1)">x</a>',
];
const results = [];
for (const md of payloads) {
  const r = await p.evaluate((m) => {
    if (typeof renderMarkdown !== 'function') return { err: 'no renderMarkdown' };
    const out = renderMarkdown(m);
    const html = out && out.html != null ? out.html : String(out);
    // insert into a detached node the way the preview does, then inspect
    const div = document.createElement('div'); div.innerHTML = html;
    return {
      html: html.slice(0, 160),
      hasScriptTag: /<script/i.test(html),
      hasOnHandler: /\son\w+\s*=/i.test(html),
      hasJsHref: [...div.querySelectorAll('a[href]')].some(a => /^\s*(javascript|data|vbscript|file):/i.test(a.getAttribute('href') || '')),
      hasImg: !!div.querySelector('img'),
    };
  }, md);
  results.push({ md: md.slice(0, 40), ...r });
}
await p.waitForTimeout(300);
console.log(JSON.stringify({ alertFired, wxss: await p.evaluate(() => window.__xss || false), results }, null, 1));
await b.close();
