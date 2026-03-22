import { chromium } from 'playwright';

async function recordDemo() {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: { dir: './demo-recordings/', size: { width: 1920, height: 1080 } }
  });
  const page = await context.newPage();

  console.log('Navigating to app...');
  await page.goto('http://localhost:8000', { waitUntil: 'networkidle', timeout: 30000 });
  
  // Wait for loading to finish and vehicles to appear
  console.log('Waiting for app to load...');
  await page.waitForTimeout(8000);

  // ACT 1: Show the living city (15 seconds)
  console.log('ACT 1: Living city...');
  await page.waitForTimeout(15000);

  // ACT 2: Point at the problem (10 seconds)
  console.log('ACT 2: The problem...');
  // Hover over the stopped counter
  await page.hover('#stopped-count');
  await page.waitForTimeout(10000);

  // ACT 3: Click Enable Green Wave (the hero moment)
  console.log('ACT 3: Enable Green Wave...');
  await page.waitForTimeout(3000); // dramatic pause
  await page.click('#btn-green-wave');
  console.log('Green Wave enabled!');
  
  // Wait for hero car and corridors to appear
  await page.waitForTimeout(20000);

  // ACT 4: Click heatmap
  console.log('ACT 4: Heatmap...');
  await page.click('#btn-heatmap');
  await page.waitForTimeout(8000);
  // Disable heatmap
  await page.click('#btn-heatmap');

  // ACT 5: Speed up to 50x for time-lapse
  console.log('ACT 5: Speed up...');
  await page.click('.speed-btn[data-speed="50"]');
  await page.waitForTimeout(10000);
  
  // Slow back down
  await page.click('.speed-btn[data-speed="5"]');
  await page.waitForTimeout(5000);

  // ACT 6: Disable Green Wave
  console.log('ACT 6: Disable...');
  await page.click('#btn-green-wave');
  await page.waitForTimeout(5000);

  // Final hold
  console.log('Final hold...');
  await page.waitForTimeout(3000);

  // Close and save video
  await context.close();
  await browser.close();
  
  console.log('Demo recorded! Check demo-recordings/ folder');
}

recordDemo().catch(console.error);
