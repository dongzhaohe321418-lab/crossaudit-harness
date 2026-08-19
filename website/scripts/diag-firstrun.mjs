import { chromium } from 'playwright';
const URL = process.argv[2];
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1280, height: 860 }, deviceScaleFactor: 1 });
await p.goto(URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
await p.waitForTimeout(1200);
const d = await p.evaluate(() => {
  const fr = document.getElementById('first-run');
  const cs = fr ? getComputedStyle(fr) : null;
  const create = document.getElementById('fr-create');
  const ccs = create ? getComputedStyle(create) : null;
  const crect = create ? create.getBoundingClientRect() : null;
  const bodyCs = getComputedStyle(document.body);
  // find first visible top-level thing
  const app = document.querySelector('.app'); const hub = document.querySelector('.project-hub');
  return {
    theme: document.documentElement.getAttribute('data-theme'),
    bodyClass: document.body.className,
    bodyBg: bodyCs.backgroundColor,
    firstRun: fr ? { display: cs.display, visibility: cs.visibility, opacity: cs.opacity, position: cs.position, height: fr.offsetHeight, width: fr.offsetWidth, zIndex: cs.zIndex } : 'MISSING',
    frInnerLen: fr ? fr.innerHTML.length : 0,
    create: create ? { display: ccs.display, vis: ccs.visibility, rect: { x: crect.x, y: crect.y, w: crect.width, h: crect.height }, text: create.textContent.trim().slice(0, 40) } : 'MISSING',
    appDisplay: app ? getComputedStyle(app).display : 'none-el',
    hubDisplay: hub ? getComputedStyle(hub).display : 'none-el',
    // sample the CSS rule text for .first-run
  };
});
console.log(JSON.stringify(d, null, 2));
await b.close();
