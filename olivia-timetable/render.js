const { chromium } = require('playwright');
const SP = '/tmp/claude-0/-home-user--Claude-/747e2a73-07c1-53b8-932e-80865b123748/scratchpad/';
(async () => {
  const b = await chromium.launch();
  for (const [f, out] of [['a4.html','Olivia-Timetable-A4'],['card.html','Olivia-Timetable-Card']]) {
    const p = await b.newPage({ viewport: { width: 794, height: 1123 }, deviceScaleFactor: 3.125 });
    await p.goto('file://' + __dirname + '/' + f);
    await p.waitForLoadState('networkidle'); await p.evaluate(() => document.fonts.ready);
    await p.pdf({ path: __dirname + '/' + out + '.pdf', preferCSSPageSize: true, printBackground: true });
    await p.screenshot({ path: __dirname + '/' + out + '.png', clip: { x: 0, y: 0, width: 794, height: 1123 } });
    await p.close();
  }
  await b.close();
})();
