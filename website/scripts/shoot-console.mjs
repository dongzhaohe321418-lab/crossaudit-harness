/* Real-console screenshots for the "The real workspace" section.

   Usage: node scripts/shoot-console.mjs <app-url> [out-dir]

   <app-url> is the URL the 4.16.0 core prints on launch (CROSSAUDIT_APP_URL=...),
   for example from the source tree:

     CROSSAUDIT_APP_SUPPORT=/tmp/ca-support PYTHONPATH=src python -m crossaudit.app

   The script opens the credential-free local demo the first-run screen offers
   (no provider, no key, every surface labelled "sample"), captures the
   conversation and the same conversation with the Audit context panel open,
   and composes each capture into a window frame at 1352x912 @2x, which is the
   2704x1824 size the page declares. Downscale afterwards with
   `sips -Z 1600` and `sips -Z 960` to produce the srcSet variants. */
import { chromium } from "playwright";
import { mkdir, readFile } from "node:fs/promises";

const url = process.argv[2];
const out = process.argv[3] ?? "public";
if (!url) {
  console.error("usage: node scripts/shoot-console.mjs <app-url> [out-dir]");
  process.exit(2);
}
await mkdir(out, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1226, height: 796 },
  deviceScaleFactor: 2,
  colorScheme: "dark",
});
await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });
await page.waitForTimeout(1500);

const demoButton = await page.$("#fr-demo");
if (demoButton && (await demoButton.isVisible())) {
  await Promise.all([
    page.waitForNavigation({ waitUntil: "networkidle", timeout: 60000 }).catch(() => {}),
    demoButton.click(),
  ]);
} else {
  const demoUrl = await page.evaluate(async () => {
    const result = await window.api("/api/projects/demo", {});
    return result.url;
  });
  await page.goto(demoUrl, { waitUntil: "networkidle", timeout: 60000 });
}
await page.waitForTimeout(3500);

const scrollThreadToTop = () =>
  page.evaluate(() => {
    const thread = document.getElementById("thread");
    if (thread) thread.scrollTop = 0;
  });

await scrollThreadToTop();
await page.waitForTimeout(600);
await page.screenshot({ path: `${out}/raw-workspace.png` });

await page.click('button[aria-controls="inspector"]');
await page.waitForTimeout(600);
await page.click('#workspace-tools [data-view="audits"]');
await page.waitForTimeout(1500);
await scrollThreadToTop();
await page.waitForTimeout(400);
await page.screenshot({ path: `${out}/raw-audit.png` });

const frame = await browser.newPage({ viewport: { width: 1352, height: 912 }, deviceScaleFactor: 2 });
for (const name of ["workspace", "audit"]) {
  const png = await readFile(`${out}/raw-${name}.png`);
  const data = `data:image/png;base64,${png.toString("base64")}`;
  await frame.setContent(`<!doctype html><html><head><style>
    html,body{margin:0;background:transparent}
    .win{position:absolute;left:63px;top:44px;width:1226px;height:824px;border-radius:12px;overflow:hidden;
      background:#1c1c1e;box-shadow:0 22px 60px rgba(0,0,0,.55),0 0 0 1px rgba(255,255,255,.08)}
    .bar{height:28px;background:#2a2a2d;display:flex;align-items:center;padding:0 12px;gap:8px;
      font:600 12px -apple-system,BlinkMacSystemFont,"SF Pro Text",Helvetica,Arial,sans-serif;color:#d0d0d4}
    .bar i{width:12px;height:12px;border-radius:50%;display:inline-block}
    .bar span{margin-left:8px}
    img{display:block;width:1226px;height:796px}
  </style></head><body><div class="win"><div class="bar">
    <i style="background:#ff5f57"></i><i style="background:#febc2e"></i><i style="background:#28c840"></i><span>CrossAudit</span>
  </div><img src="${data}" alt=""></div></body></html>`);
  await frame.waitForTimeout(400);
  await frame.screenshot({ path: `${out}/crossaudit-${name}.png`, omitBackground: true });
}
await browser.close();
console.log(`wrote ${out}/crossaudit-workspace.png and ${out}/crossaudit-audit.png (2704x1824)`);
