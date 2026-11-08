/**
 * 带帧解码等待的确定性校验 —— 用于含 P.clip 帧序列的项目。
 *
 * 为什么需要它（2026-11-08 铅笔正片实测）
 * ------------------------------------------------------------------
 * 引擎自带 `ftcheck.py --determinism` → `lint.mjs --determinism` →
 * `checks.mjs` 的 shot() 是：
 *     ENGINE.renderAt(from); ENGINE.renderAt(t);   // 同一个 evaluate，纯同步
 *     return page.screenshot(...)
 * 它 **不 await window.__frameReady(t)**。而 `media.js` 的 P.clip 目标帧是
 * 异步 `im.decode()`；目标帧未解码时 tick() 直接 return，canvas 保留上一帧。
 * 于是 cold(from=0) 与 warm(from=页尾) 两条路径留下的「上一帧」不同 → 误报
 * nondeterministic，差异面积恰好等于动图框面积。
 *
 * 渲染 / 拼图 / snap 三条真实路径都会 await __frameReady（见
 * render-chunk.mjs:55、checks.mjs:210、snap.mjs:26），本脚本复刻这条路径，
 * 只是把 checks.mjs 的两次渲染都补上等待。比较逻辑与 checks.mjs 完全一致
 * （浏览器内 OffscreenCanvas 像素差，阈值 0.0005）。
 *
 * 用法：在**项目目录**下运行
 *   node <skill>/scripts/ftdeterminism.mjs
 *
 * 注意：本脚本只读，不改引擎源码。引擎是 AGPL 的独立依赖，不进本仓库。
 */
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const root = process.cwd();
const libPath = path.join(root, 'engine', 'tools', 'lib.mjs');
if (!fs.existsSync(libPath)) {
  console.error('✗ 请在项目目录下运行（需要 <项目>/engine/tools/lib.mjs）。');
  console.error('  项目由 ftnew.py 创建时会建 engine 链接；引擎由 scripts/setup.py 安装。');
  process.exit(1);
}
const libUrl = pathToFileURL(libPath).href;
const { loadEpisode, openStage, finish } = await import(libUrl);

const { L } = loadEpisode();
const pages = L.pages;
const { page } = await openStage('render');

const compare = async (a, b) => {
  if (a.equals(b)) return 0;
  return page.evaluate(async ([x, y]) => {
    const load = async (b64) => createImageBitmap(await (await fetch('data:image/png;base64,' + b64)).blob());
    const [ia, ib] = await Promise.all([load(x), load(y)]);
    const px = (img) => { const c = new OffscreenCanvas(img.width, img.height); const g = c.getContext('2d'); g.drawImage(img, 0, 0); return g.getImageData(0, 0, img.width, img.height).data; };
    const da = px(ia), db = px(ib);
    let n = 0;
    for (let i = 0; i < da.length; i += 4) {
      if (Math.abs(da[i] - db[i]) + Math.abs(da[i + 1] - db[i + 1]) + Math.abs(da[i + 2] - db[i + 2]) > 48) n++;
    }
    return n / (da.length / 4);
  }, [a.toString('base64'), b.toString('base64')]);
};

let bad = 0;
for (const p of pages) {
  const mid = (p.start + p.end) / 2;
  const shot = async (from) => {
    await page.evaluate(async ({ from, t }) => {
      ENGINE.renderAt(from);
      if (window.__frameReady) await window.__frameReady(from);
      ENGINE.renderAt(t);
      if (window.__frameReady) await window.__frameReady(t);
    }, { from, t: mid });
    return page.screenshot({ type: 'png' });
  };
  const a = await shot(0);
  const b = await shot(p.end - 0.1);
  const changed = await compare(a, b);
  const ok = changed <= 0.0005;
  if (!ok) bad++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${p.id}  mid=${mid.toFixed(2)}s  差异 ${(changed * 100).toFixed(3)}%`);
}
console.log(`\n${pages.length - bad}/${pages.length} 页在真实渲染路径下像素一致`);
finish();
if (bad) process.exitCode = 1;
