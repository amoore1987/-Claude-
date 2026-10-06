// Render SVG logos to PNG (transparent) and PDF (vector) with headless Chromium.
// usage: node render.js <svgDir> <outDir> [--png-sizes 2048,4096] [--pdf] [files...]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
const svgDir = args[0];
const outDir = args[1];
let pngSizes = [2048];
let doPdf = false;
const files = [];
for (let i = 2; i < args.length; i++) {
  if (args[i] === '--png-sizes') pngSizes = args[++i].split(',').map(Number);
  else if (args[i] === '--pdf') doPdf = true;
  else files.push(args[i]);
}
const svgs = files.length ? files : fs.readdirSync(svgDir).filter(f => f.endsWith('.svg'));

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch();
  for (const f of svgs) {
    const svg = fs.readFileSync(path.join(svgDir, f), 'utf8');
    const m = svg.match(/viewBox="0 0 (\d+) (\d+)"/);
    const vw = Number(m[1]), vh = Number(m[2]);
    const base = f.replace(/\.svg$/, '');
    for (const target of pngSizes) {
      const scale = target / Math.max(vw, vh);
      const ctx = await browser.newContext({ viewport: { width: vw, height: vh }, deviceScaleFactor: scale });
      const page = await ctx.newPage();
      await page.setContent(`<!doctype html><html><head><style>html,body{margin:0;padding:0;background:transparent}svg{display:block;width:${vw}px;height:${vh}px}</style></head><body>${svg}</body></html>`);
      const out = path.join(outDir, `${base}-${Math.round(vw * scale)}px.png`);
      await page.screenshot({ path: out, omitBackground: true, type: 'png' });
      console.log('png', out);
      await ctx.close();
    }
    if (doPdf) {
      const ctx = await browser.newContext({ viewport: { width: vw, height: vh } });
      const page = await ctx.newPage();
      await page.setContent(`<!doctype html><html><head><style>@page{size:${vw}px ${vh}px;margin:0}html,body{margin:0;padding:0}svg{display:block;width:${vw}px;height:${vh}px}</style></head><body>${svg}</body></html>`);
      const out = path.join(outDir, `${base}.pdf`);
      await page.pdf({ path: out, width: `${vw}px`, height: `${vh}px`, printBackground: true, margin: { top: 0, right: 0, bottom: 0, left: 0 } });
      console.log('pdf', out);
      await ctx.close();
    }
  }
  await browser.close();
})();
