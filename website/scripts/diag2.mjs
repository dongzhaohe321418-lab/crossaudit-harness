import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1280, height: 860 } });
await p.goto(process.argv[2], { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1000);
const chain = await p.evaluate(() => {
  const out = [];
  let el = document.getElementById('first-run');
  while (el && el.tagName !== 'HTML') {
    const cs = getComputedStyle(el);
    out.push({ tag: el.tagName, cls: (el.className||'').toString().slice(0,40), display: cs.display, h: el.offsetHeight, w: el.offsetWidth, pos: cs.position });
    el = el.parentElement;
  }
  return out;
});
console.log(JSON.stringify(chain, null, 1));
await b.close();
