// 用 Playwright 把预览页渲染成 PNG（需先安装 playwright + chromium）
// 运行：node screenshot.js
const { chromium } = require("playwright");
const { pathToFileURL } = require("url");
const path = require("path");

const htmlPath = path.resolve(__dirname, "tongwangas-shandong-card-preview.html");
const outPath = path.resolve(__dirname, "tongwangas-shandong-card-preview.png");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 520, height: 2600 },
    deviceScaleFactor: 2,
  });
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "domcontentloaded" });
  // 等待卡片渲染与字体/布局稳定
  await page.waitForTimeout(1200);
  await page.screenshot({ path: outPath, fullPage: true });
  console.log("SHOT_DONE ->", outPath);
  // 图片已落盘，但本机 browser.close() 偶发挂起，直接结束进程避免脚本假死
  await browser.close().catch(() => {});
  process.exit(0);
})().catch((err) => {
  console.error("SHOT_FAIL", err);
  process.exit(1);
});
