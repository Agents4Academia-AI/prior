/* Usage: NODE_PATH=/path/to/node_modules node export_pdf.cjs /path/to/Chrome */
const { chromium } = require('playwright');
const path = require('node:path');
const fs = require('node:fs');
(async () => {
  const browser = await chromium.launch({headless:true, ...(process.argv[2] ? {executablePath:process.argv[2]} : {})});
  try {
    const page = await browser.newPage({viewport:{width:1600,height:948},reducedMotion:'reduce',offline:true});
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.goto('file://' + path.join(__dirname,'PRIOR.html'));
    const summary = await page.evaluate(() => ({slides:deck.slides.length, main:deck.slides.filter(s=>!s.backup).length, notes:deck.slides.some(s=>s.notes.trim()), nodes:document.querySelectorAll('[data-graph="global"] .point').length,papers:document.querySelectorAll('.scoper-paper').length}));
    if(summary.slides!==11 || summary.main!==10 || summary.notes || summary.nodes!==581 || summary.papers!==152) throw Error(JSON.stringify(summary));
    for (let i=0;i<summary.slides;i++) {
      const steps = await page.evaluate(i=>deck.slides[i].steps,i);
      for(let k=0;k<=steps;k++) await page.evaluate(([i,k])=>deck.go(i,k),[i,k]);
    }
    await page.evaluate(()=>deck.go(0));
    if(errors.length) throw Error(errors.join('\n'));
    await page.emulateMedia({media:'print'});
    await page.pdf({path:path.join(__dirname,'PRIOR-AIASci-2026.pdf'),printBackground:true,preferCSSPageSize:true});
    console.log(JSON.stringify({ ...summary, browserErrors:errors, pdf:'PRIOR-AIASci-2026.pdf' }));
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1)});
