# 矢量动效接入手册 · 实测记录与边界

> 2026-11-08 建 skill 并跑通单页样板时的记录。
> **每一条「已核实」都标了证据来源；「待实测」一律不写成规则。**
> 可复现样板：本仓库 `examples/sample/`（单页 9.32s，lint 0 错 0 提醒）。
> 素材随包提供，不联网、不花钱就能跑通全流程。正片实测见 §2.5。

---

## 1. 结论

GPT Image 2.6 Flare 的 GIF / SVG **不是视频模型的替代品**：

- SVG 是静态矢量，动效靠引擎时间轴加；
- GIF 在 apiz 通道最多 9 帧、约 1.8 秒循环，是「微动效」不是「视频」。

能兑现的价值是：**把纯代码画的粗糙图形升级为精致矢量图解 + 局部真实微动效**，
而「讲到哪画到哪」的音画对齐、确定性渲染、分段缓存全部保留。

---

## 2. 已核实（有证据，可当依据）

### 2.1 引擎侧（读源码）

| 事实 | 证据 |
|---|---|
| `P.clip` 帧索引 `idxAt(lt)` 是页内时间的纯函数，支持 `loop/pingpong/timeMap/fps/speed/from/to/start` | `engine/runtime/media.js:87-122` |
| `window.__frameReady(t)` 等帧解码完再重绘；render / snap / checks 三条路都 await 它 | `media.js:46-49`、`render-chunk.mjs:55`、`snap.mjs:26`、`checks.mjs:210` |
| 分段缓存 digest **不 hash `assets/`**，只 hash runtime / lib / styles / **extras** / index.html / META / pages | `engine/tools/render.mjs:136-144` |
| `Builder` 构造函数有 `this.svg = s('svg',…)` —— 实例属性 `svg` 是画布 SVG 元素 | `engine/runtime/core.js:88` |
| `Builder` 只挂在 `PV` 上，不是全局标识符；`core.js` 里是 IIFE 内的 class | `core.js:81-101`、`:341` |
| `boot.js` 按 `META.extras` 顺序加载，位置在 core.js 之后、engine.js 之前 | `engine/boot.js:30-38` |

### 2.2 模型侧（真实调用 + 官方规格）

| 事实 | 证据 |
|---|---|
| 模型 `apiz/gpt-image-2.6-flare`，异步任务，返回 `result.images[0].url` + `price` | 两次 `apiz generate --wait --json` 实测 |
| `frame_count` **schema `maximum: 9`**（文档表格写「2–16」是错的，schema 才是权威） | `GET /api/v3/models/apiz/gpt-image-2.6-flare` 的 `params_schema` |
| `output_format` 为 png/jpeg/webp/gif/svg；文档标注 **gif/svg 只能文生图** | 同上 |
| `transparency` 只管 PNG；`svg_author_model` 有固定作者附加费 | 同上 |
| SVG 返回 CDN 上的 `.svg` 文件（`image/svg+xml`），不是内嵌代码 | 实测下载 3311 bytes |
| 生成的 SVG 是 `viewBox 0 0 1024 1024`，纯 path/circle/rect + 渐变 defs，**无脚本/外链/位图/文字** | 实测 SVG 全文 |
| GIF 返回 `.gif`，实测 **真 9 帧、512×512、每帧 200ms** | Pillow 逐帧读取 |
| `size:"1K"` 下静态 SVG 是 1024²，但 GIF 给 512² —— 两者尺寸档不等价 | 两次实测对比 |
| `aspect_ratio` 对 SVG 真的生效：`16:9` → `viewBox 0 0 1376 768`、`3:2` → `1264 848`、`1:1` → `1024 1024`。**页面框按这个比例给，能零白边铺满** | 2026-11-08 铅笔正片 11 张 SVG 全部核对 |
| 线稿类 SVG 的颜色写在 `fill=` / `stroke=` 属性上（父 `<g>` 定义、`fill="none"`），没有 `<style>` 标签 → 清洗不会掉色 | 同上，正则统计 4 张样本：style 属性 0 个 |
| 成本随复杂度浮动：SVG 16–23 积分、GIF 25–26 积分；`size:"1K"` 下 GIF 恒为 512²、9 帧、每帧 200ms | 同上，铅笔正片 15 次调用逐条打印 |
| 单次成本：SVG 23 积分（¥0.23）/ 48 秒；GIF 25 积分（¥0.25）/ 14 秒 | 实测 `price` 与 `created_at/completed_at` |
| 官方：GIF 原生 2–64 帧、默认 9×200ms；SVG 静态、无脚本/外链/内嵌位图、n=1、edits 不返回 | OpenAI 2026-11-04 发布规格，多源一致 |
| 官方定价 $5 / $8 / $30 每 1M（文本输入/图像输入/图像输出），Flare 与 Sunburst 同价 | 同上 |
| `apiz` CLI 有 `generate --params --wait`、`tasks`、`transfer`、`upload`、`account balance` | `apiz --help` 等 |

### 2.3 依赖与验收环境（中性描述，不含任何账号信息）

| 依赖 | 用途 | 是否必需 |
|---|---|---|
| Python 3.9+ / 标准库 `urllib` | 素材脚本主体 | ✅ |
| Pillow | GIF 拆帧 | ✅（拆帧时） |
| `apiz` CLI + 已配置的 key | **生成新素材** | ⭕ 可选；复用 `assets/raw/` 或 `examples/` 不需要 |
| Node ≥ 22.19 / Chrome 或 Edge / ffmpeg | 渲染与质检 | ✅（出片时） |
| `requests` | — | ❌ 不用；脚本走 CLI + urllib |

- 渲染 worker 默认 1：引擎默认 12 在 11 页以上长片会 OOM（2026-11-08 铅笔片实测，
  12 workers 两次崩、1 worker 一次成）。`ftrender.py` 已把 `--workers` 默认值设为 1，可用参数调。

### 2.4 端到端样板结果

```
ftasset.py  → 1 SVG (2188 chars 清洗后) + 1 GIF (9 帧 512²)   ¥0.48
ftvoice.py  → 3 条 cue / voice.js / 字幕.srt
ftcheck.py  → lint 0 错 0 提醒，p01 0s→9.32s（讲完 6.82s）
snap 7.2s   → 终态单帧所有元素完整，无遮挡、无重叠
```

### 2.5 正片端到端结果（2026-11-08 · `pencil-craft-2026`）

11 页 / 33 句 / 121.9s，11 个 SVG 逐笔生长 + 10 个 GIF 拆帧循环，混排手绘的
机械运动、配比条、涂层横条、计数器、勾选理由、相机轻推和收束页绕环指针。

| 验收项 | 结果 |
|---|---|
| 素材 | 11 SVG 全部合法、10 GIF 均为真 9 帧 512²；本次素材花费 ¥2.27 |
| lint | 0 错 0 提醒 |
| 11 页拼图 + 终态单帧 | 逐页看过，无遮挡 / 缺元素 / 字幕带越界 |
| 确定性 | `ftdeterminism.mjs` 11/11 页 0.000% 差异 |
| 成片 | 1920×1080 / 24fps / H.264+AAC / 33 条字幕，ffmpeg 全解码无错 |
| 视觉融合度 | **用户确认「AI 素材和手绘版面非常兼容，就是这样效果」** |

正片不是样板，说明这条管线能撑住完整讲解片，而不只是单页 demo。

---

## 3. 参数边界速查

| 参数 | apiz schema | 官方 | 本 skill 默认 |
|---|---|---|---|
| `output_format` | png/jpeg/webp/gif/svg | 同 | 由 spec 条目类型强制 svg / gif |
| `frame_count` | **2–9**，默认 9 | 2–64，默认 9 | 9 |
| `frame_duration_ms` | 20–2000，默认 200 | 同 | 200 |
| `aspect_ratio` | 10 种 + auto | — | `1:1` |
| `size` | 1K / 2K / 4K | — | `1K` |
| `quality` | low/medium/high/xhigh/max | — | `low` |
| `complexity` | low/medium/high，不单独收费 | 同 | `low` |
| `svg_author_model` | gpt-5.5 / gpt-5-mini | — | `gpt-5-mini`（省固定附加费） |
| `reference_image_urls` | 1–16 张公网 URL | generations 支持、edits 不支持 | **本 skill 不用**（见待实测） |

> `gif/svg 只能文生图` 是 apiz 文档原话。官方说的是「edits 端点不返回 gif/svg」，
> generations 其实可以带参考图。**两者说法有出入，未实测前不把「能/不能用参考图」写成结论。**

---

## 4. 流水线（复现样板）

从仓库根目录执行（`<skill>` = 本仓库目录，`<项目>` 建议放在 skill 之外）：

```bash
# ① 一次性安装（拉引擎 + npm 依赖）
python <skill>/scripts/setup.py
pip install Pillow edge-tts          # 拆帧 / 免费配音

# ② 离线跑通自带样板：复制输入文件到项目位置，不调用任何付费 API
cp -r <skill>/examples/sample <项目>

# ③ 素材链路（复用 assets/raw/ 里随包提供的 SVG + GIF）
python <skill>/scripts/ftasset.py <项目> --spec <项目>/assets.json

# ④ 配音 / 质检 / 确定性 / 渲染
python <skill>/scripts/ftvoice.py <项目>
python <skill>/scripts/ftcheck.py <项目>
node <skill>/scripts/ftdeterminism.mjs              # 在项目目录里跑
python <skill>/scripts/ftrender.py <项目> --fps 24
```

`ftasset.py` 自动把 `lib/motion-svg.js` 装进 `extras/`，并检查 `script.js` 的
`META.extras` 四项是否齐全（顺序不能反：`svg-assets.js` → `clips.js` →
`asset-manifest.js` → `motion-svg.js`）。
已有 `assets/raw/<name>.*` 会跳过 API（幂等，不重复花钱）；`--force` 才重抽。
**只要不删 `assets/raw/`，整条流程不需要 apiz、不需要 key、不产生费用。**

---

## 5. 踩坑清单（都是实测踩出来的）

### ① `P.svg` 不能用 —— 实例属性遮蔽原型方法 ⭐ 最容易踩

`Builder` 构造函数里 `this.svg = s('svg', …)` 是这一页的画布 SVG 元素。
把组件方法挂成 `B.svg` 后，`PV.Builder.prototype.svg` 确实是 function，
但 `P.svg` 取到的是那个 DOM 对象 → 页面 build 报 **`P.svg is not a function`**。

**症状很迷惑**：组件挂载成功、lint 只报「wrong API use」，看不出是命名冲突。
浏览器里探 `typeof PV.Builder.prototype.svg` = function、`typeof P.svg` = object 才定位到。

**修法**：方法改名 `P.vector()`。同类先例：引擎全局 `window.STAGE` 也不能占用。

### ② `Builder` 不是全局标识符

`core.js` 的 `Builder` 是 IIFE 内的局部 class，只通过 `PV.Builder` 暴露。
组件里写裸 `Builder.prototype` 会在**加载阶段**就 `ReferenceError`，
extras 的加载错误不被 engine 的 error handler 捕获（它只抓 `pages/*.js`），
于是页面同样只报「P.vector is not a function」。

**修法**：`const { h, clamp, ease, col, Builder } = PV;` —— 和 `media.js` 一样从 PV 解构。

### ③ 换素材不重渲

`render.mjs` 的 digest 不 hash `assets/`。素材重新生成、文件名不变 → 静默用旧帧。

**修法**：`ftasset.py` 把 SVG 文本 + 所有 GIF 帧字节的 sha256 写进
`extras/asset-manifest.js`（extras 会被 digest hash），素材一变 digest 就变。
绕过 `ftasset.py` 手工换图时必须自己 `mv out/chunks out/.chunks-before-fix`。

### ④ `.gif` 不能直接 `P.img`

浏览器按 wall clock 播 GIF，与 `lt` 无关 → 同一 `t` 每次渲染结果不同，
分段缓存 / 确定性校验 / 任意跳转全废。必须拆成帧序列交给 `P.clip`。

### ⑤ SVG 里的动画标签必须剥掉

`<animate*>` / `<set>` / `<style>` 里的 animation / transition / 外链字体位图同理。
`ftasset.py` 的 `sanitize_svg()` 在落盘前处理，并同时剥掉 `<text>` ——
文字交给 `P.text` 手绘，避免字体缺字形和术语错误。

> 附带影响：某些 SVG 靠 `<style>` 定义颜色，剥掉后会掉色。
> 这时用 `P.vector(..., { stroke:'ink' })` 补回（可选手法，不是硬要求）。

### ⑥ 429 是 API Key 的独立额度，不是账户余额、也不是并发 ⭐ 批量时最容易踩

2026-11-08 铅笔正片要生成 21 个素材，先后报：

```
apiz: HTTP 429 — 计费失败: API Key 额度不足，剩余额度: 7.00，本次需要: 23
apiz: HTTP 429 — 计费失败: API Key 额度不足，剩余额度: 26.00，本次需要: 40
```

**证据链（据此排除掉一个我自己的错误归因）**：

| 观察 | 结论 |
|---|---|
| 3 个进程并发时两组报 429 | 最初误判为并发预扣竞态 |
| **停掉并发、单进程串行全量补跑，仍报「剩余额度 8.00」** | 与并发无关，误判被推翻 |
| `apiz account balance` 同期一直显示有余额 | 报错里的「额度」不是账户余额，是另一个维度 |
| 用户在控制台提高 Key 额度后，`--only sandwich` 立刻成功、实扣 23 积分 | 确认是 **API Key 自带独立额度** 用尽 |

**修法**：`apiz account balance` 有钱不代表能生成。遇到这条 429 要去控制台
提高/重置 **API Key 额度**（不是充值账户）；恢复后直接重跑全量 `ftasset.py`。
它是幂等的（`assets/raw/` 已有就跳过、不重复花钱），缺的会补上、已完成的瞬间跳过，
不会浪费积分。批量串行跑更稳妥，但串行本身不能绕过额度限制。

### ⑦ AI 会把「没求值的算式 / 英文单词」写进 SVG 数值属性 ⭐ 静默缺笔

2026-11-08 铅笔正片 11 个 SVG 里有 2 个中招，浏览器只在 console 报一句，
**画面上直接丢图形，lint 完全查不出**：

```
console Error: <line> attribute x2: Expected length, "132+714.28571428…"   ×6 条刻度线
console Error: <path> attribute d: Expected number, "…100 540 70 520  eighty 480"
```

- `hb-scale.svg`：6 条刻度线的 `x1/x2` 写成 `132+142.857…` 这类未求值加法式
- `hex-profile.svg`：一条弧线 path 的 `d` 里混进单词 `eighty`

**处理**（`ftasset.py` 的 `sanitize_svg()` 已内置，复用 `assets/raw/` 重跑不花钱）：

| 情况 | 做法 |
|---|---|
| 几何属性是纯数字加法式 | 就地求和成数值（`132+142.857` → `274.857`） |
| `d` 去掉数字后还剩非路径命令字母 | 整条元素剔除（浏览器本来也会丢弃它，避免半截图形） |
| 其他非法值 | 不乱改，保留原样 |

修完用正则全量扫一遍 `x1/x2/…/d` 再渲染。**这是保守降级，不是「AI SVG 一定干净」的保证**——
每批新素材仍要看一次 console。

### ⑧ `ftcheck.py --determinism` 对帧序列会误报 ⭐ 别据此判定画面不确定

11 页正片带 10 个 `P.clip` 时，引擎自带校验报 **8 页 nondeterministic**
（1.56%–11.03% 差异，数值恰好等于各页动图框面积）。追到
`engine/tools/checks.mjs:110`：

```js
const shot = async (from) => {
  await page.evaluate(({ from, t }) => { ENGINE.renderAt(from); ENGINE.renderAt(t); }, …);
  return page.screenshot({ type: 'png' });   // ← 不 await window.__frameReady(t)
};
```

`media.js` 的 clip 目标帧靠 `im.decode()` 异步加载，未解码时 `tick()` 直接
`return`，canvas 保留上一帧；cold(from=0) 和 warm(from=页尾) 留下的「上一帧」
不同 → 误报。**渲染 / 拼图 / snap 三条真实路径都 await `__frameReady`**
（`render-chunk.mjs:55`、`checks.mjs:210`、`snap.mjs:26`），只有 lint 这条没等。

**正确做法**：用本 skill 的 `scripts/ftdeterminism.mjs`（复刻 checks.mjs 的
两次渲染与像素比较，但每次 `renderAt` 后补 `await __frameReady`）。
铅笔正片实测 **11/11 页 0.000% 差异**。不要改引擎源码（AGPL、独立依赖）。

---

## 6. 已废规则清单

> 用户明确要求：把被推翻的假设连同「为什么错」留在文档里，防止以后又被写回去。

- ~~**「GIF / SVG 可以替代视频模型，形成更丰富的视频动效」**~~
  → 已废。SVG 官方定义是静态矢量、不带脚本；GIF 在 apiz 通道最多 9 帧 1.8 秒循环。
  它能补的是画面质感和局部微动效，不是时间轴叙事能力。

- ~~**「frame_count 可以设到 16」**~~
  → 已废。`gpt-image-new-llms.md` 表格写「2–16」，但 `params_schema` 的 `maximum` 是 **9**。
  以 schema 为准；文档描述文字自相矛盾（描述里写 2–16，schema 写 2–9）。

- ~~**「生成的 GIF 可以像 PNG 一样直接 `P.img` 放上去」**~~
  → 已废。破坏 `renderAt(t)` 纯函数契约，见坑 ④。

- ~~**「素材放 `assets/`，改了会自动触发重渲」**~~
  → 已废。`render.mjs` 不 hash `assets/`，见坑 ③。

- ~~**「组件方法叫 `P.svg` 最直观」**~~
  → 已废。与 `Builder` 实例属性冲突，见坑 ①。

- ~~**「429 是并发预扣池被占满，串行就能绕开」**~~
  → 已废（2026-11-08 自我纠错）。当时只看到「并发时报错、样板串行成功」，
  没做「停掉并发后串行重试」这个对照实验就下了结论。后来串行补跑同样报
  「剩余额度 8.00」，提高 API Key 额度后立刻恢复 → 真因是 Key 独立额度，
  与并发无关。详见坑 ⑥。**教训：报错文案里的维度要先查清，别拿时间上的先后当因果。**

---

## 7. 待实测（**不能写成规则**，需要时先做一次最小调用）

1. apiz 的 `gif`/`svg` 能否真的传 `reference_image_urls`（apiz 说「只能文生图」，官方 generations 说法不同）——
   这决定跨页风格一致性有没有硬保障。
2. 9 帧循环的**首尾接缝**与帧间一致性；社区实测反馈「运动不均匀、回到第一帧跳变明显」，
   `P.clip` 的 `pingpong` 能否缓解，未在本片里验证。
3. 高分辨率 GIF（2K/4K）的像素预算限制 —— 实测 `1K` 档 GIF 只给 512²。
4. `quality` 提到 medium/high 后成本与耗时的实际曲线。
5. 内联 SVG 的 `stroke-dashoffset` 在**不同风格包 / 竖屏 / 相机推镜**下是否稳定。
6. `P.vector` 的 `stroke` 换色对「父 `<g>` 上定义 stroke、子 path 无 stroke」的 SVG 不生效
   （实测的 bulb-line 就是这种结构）—— 需要时改成向上查找继承色。
7. ~~**视觉融合度**~~ → **已确认，移出待实测**（2026-11-08）：用户看完单页样板后
   明确表示「AI 素材和手绘版面非常兼容，就是这样效果」，随后据此完成 11 页正片。
   黑白细线稿 + 彩色写实微动图的搭配是保留的既定风格，不是待定问题。

---

## 8. 一版一交付

> 用户级约定：每完成一版（渲染出图），立即交付给用户看，明确说明「这一版已完成，等你确认再改」。
> **造型、配色、比例、构图的美学调整必须先问**，不许在用户没看到上一版时连续做多轮自我评审。

所以本 skill 的实际推进是：先做**一页样板** → 出拼图 + 终态单帧 + 成片 → 交付 →
等用户确认视觉融合度 → 才铺开做 11 页正片。样板已在 2026-11-08 得到确认，
正片也已完成交付。**后续做新题材时仍按一版一交付，不在用户没看到上一版时连改多轮。**
