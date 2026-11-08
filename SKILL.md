---
name: whiteboard-teacher-video-motion
version: 1.0.0
display_name: 矢量动效讲解视频
display_name_en: Vector Motion Explainer Video
description: 独立可用的手绘讲解视频 skill。在「代码逐笔绘制」的白板讲解片里，加入 GPT Image 2.6 Flare 生成的原生 SVG 矢量图解（由时间轴驱动逐笔生长）与 GIF 拆帧后的局部真实微动效，解决纯手绘图形质感粗糙、缺少真实动态的问题。自带完整运行时脚本、安装器、页面 API 手册与一个不联网不花钱的单页样板；保留分段缓存、确定性渲染、字幕与音画对齐。当用户要求「画面更精致」「矢量图解」「加一点真实动效」「动图解说法」「AI 生图接入讲解视频」时使用。触发词：矢量动效、精致图解、动效增强、SVG 讲解视频、GIF 微动效、vector motion explainer。
description_zh: 独立的手绘讲解视频 skill：用 AI 生成的原生 SVG 做精致矢量图解、GIF 做局部微动效，两者都接进 frametell 的纯函数时间轴，不破坏音画对齐与确定性渲染。安装后即可离线跑通自带样板。
description_en: A standalone whiteboard explainer-video skill: native AI-generated SVG diagrams drawn stroke by stroke on the timeline, plus GIF frame sequences as local micro-motion, both wired into frametell's pure-function timeline. Ships with its own runtime, installer, docs and an offline sample.
license: MIT
---

# 矢量动效讲解视频 · whiteboard-teacher-video-motion

**这是一个完整、独立、可直接安装的 skill。** 仓库自带运行时脚本、安装器、页面 API 手册、
免费配音后端、单页离线样板。不需要先装别的项目（引擎由 `scripts/setup.py` 自动获取）。

它和上游 [`whiteboard-teacher-video`](https://github.com/liangdabiao/whiteboard-teacher-video)
同源：保留了「讲到哪画到哪」的确定性、可秒级重渲、分段缓存；只补上纯代码绘图最弱的一层——
图形质感与局部真实动态。

| 需求 | 用什么 | 时间轴怎么驱动 |
|---|---|---|
| 精致的图解、图标、结构图 | GPT Image 2.6 Flare 的**原生 SVG** | 内联进 DOM，由 `P.vector()` 按 `lt` 驱动 `stroke-dashoffset` 逐笔生长 |
| 局部「活起来」的微动效 | 同模型的 **GIF** | 拆成 `f000.jpg…` 帧序列，交给引擎自带的 `P.clip()` 按 `lt` 取帧 |
| 文字、箭头、强调、相机 | **照旧手绘** | `P.text` / `P.arrow` / `P.mark` / `P.cam` |

文字仍由手绘 `P.text` 出（不让 AI 在 SVG 里写字）：字体、术语、事实都要能人工核对。
用户已确认「AI 素材和手绘版面非常兼容」，黑白细线稿 + 彩色写实微动图是既定风格。

---

## 0. 安装（第一次必做）

```bash
git clone https://github.com/liangdabiao/whiteboard-teacher-video-motion.git
cd whiteboard-teacher-video-motion
python scripts/setup.py          # 拉 AGPL 引擎(约 16MB) + npm install(约 130MB)
pip install Pillow edge-tts      # GIF 拆帧 / 免费中文配音
```

需要 Python 3.9+、Node ≥ 22.19、Chrome 或 Edge、git。
`setup.py` 会自检浏览器、ffmpeg、Node、Pillow、配音后端，并把缺失项打印出来。

**`apiz` CLI 是可选的**：只有「生成新素材」时才需要（需账号、按量计费）。
仓库 `examples/sample/assets/raw/` 里已放好 1 个 SVG + 1 个 GIF，
不联网、不花钱就能跑通全流水线。**先跑离线样板，确认环境，再决定要不要接付费素材。**

WorkBuddy 用户：把整个仓库目录放到 `<工作区>/.workbuddy/skills/whiteboard-teacher-video-motion/`
即可被识别；任何目录下的独立 clone 也能直接跑脚本。

---

## 1. 先搞清楚一件事（别把它当视频模型）

核实过官方规格与 apiz 的 `params_schema` 后：

- **SVG 是静态矢量**：无脚本、无外部资源、无内嵌位图，`n=1`，编辑接口不返回。
  它本身**不带任何动效** —— 动效是本 skill 的时间轴加的。
- **GIF 是微动图**：官方 2–64 帧，**apiz 通道最多 9 帧**（`params_schema` 的 `maximum: 9`）；
  默认 9 帧 × 200ms ≈ 1.8 秒循环。
- 两者只能用 generations 接口，**不能用 edit 接口做局部精修**，改一处只能重新抽卡。

所以能兑现的不是「动效更丰富」，而是**画面质感 + 局部真实动态**，
音画对齐仍由引擎保证。想整片变成 AI 生成画面，不要用这个 skill。

---

## 2. 引擎契约（红线）

**整片是时间的纯函数**：`ENGINE.renderAt(t)` 渲染第 `t` 秒，与之前播放过什么无关。
由此才有分段缓存、并行渲染、任意跳转、确定性校验。

| 红线 | 原因 |
|---|---|
| **不要把 `.gif` 直接塞 `P.img`** | 浏览器按自己的时钟播 GIF，与 `lt` 无关 → 同一 `t` 每次渲染结果不同 |
| **SVG 里的 `<animate>` / SMIL / CSS animation / transition / 外链 / 位图必须剥掉** | 同上；`ftasset.py` 落盘前已自动清洗 |
| **页面里禁止 `Math.random()` / `Date.now()` / `rAF`** | 契约；随机走 `PV.rng(seed)` |
| **素材重新生成后，`extras/` 里的哈希必须跟着变** | 引擎分段缓存 digest **不 hash `assets/`**。`ftasset.py` 写的 `asset-manifest.js` 就是干这个的 |
| **`META.extras` 顺序不能反** | `boot.js` 按序加载：`svg-assets.js` → `clips.js` → `asset-manifest.js` → `motion-svg.js` |

**生成不确定，渲染确定** —— 素材是抽卡，但一旦落盘成文件，
后面每一帧渲染、每一页重渲、每一次确定性校验都与纯手绘版完全一样。

---

## 3. 工作流

`<skill>` = 本仓库目录；`<项目>` 必须放在 **skill 目录之外**（`ftnew.py` 会建 engine 链接，
放在里面会形成目录环）。

```
① 读 references/storyboard-method.md → 写 storyboard.json
② ★★★ 停下来，把分镜念给用户确认 ★★★          ← 唯一强制闸门，不跳过
③ 写 script.js（口播 cue）+ 填 META.extras 四项
④ python <skill>/scripts/ftnew.py <项目> --title "..." --style whiteboard
⑤ python <skill>/scripts/ftasset.py <项目> --spec <项目>/assets.json   ← 新增
⑥ python <skill>/scripts/ftvoice.py <项目>
⑦ 逐页写 pages/pNN.js（P.vector / P.clip / 手绘混排）
⑧ python <skill>/scripts/ftcheck.py <项目>     → lint + 每页拼图，逐页看图
⑨ cd <项目> && node engine/tools/snap.mjs --only pNN <讲完时刻> --sheet pNN-final
⑩ cd <项目> && node <skill>/scripts/ftdeterminism.mjs   ← 含 P.clip 必跑
⑪ python <skill>/scripts/ftrender.py <项目> --fps 24
⑫ ★ 交付给用户看 ★ → 等确认再改
```

第 ⑤ 步产出（全在项目目录内）：

```
assets/raw/<name>.svg|.gif       原始下载，断点续用；已存在就跳过 API（不重复花钱）
assets/svg/<name>.svg            清洗后的 SVG
assets/clips/<name>/f000.jpg…    GIF 拆出的帧序列
extras/svg-assets.js             window.SVG_ASSETS（同步内联，build 阶段不 fetch）
extras/clips.js                  window.CLIP_FRAMES（帧数注册）
extras/asset-manifest.js         素材哈希，让缓存感知变化
extras/motion-svg.js             从本仓库 lib/ 自动复制过去
```

`ftasset.py` 还会修 AI 写坏的 SVG 数值属性（未求值算式就地求和、无法解析的 `d` 整条剔除）；
每批新素材仍要看一次浏览器 console，别假定 AI 输出一定合法。见手册坑 ⑦。

> **含 `P.clip` 的项目别用 `ftcheck.py --determinism` 下结论**：引擎那条校验
> 不 await `__frameReady`，会对帧序列误报（实测 11 页误报 8 页）。
> 用 ⑩ 的 `ftdeterminism.mjs`，它复刻同样比较但补上等待。见手册坑 ⑧。

> **批量素材一次跑完，中途失败直接重跑全量**：`ftasset.py` 幂等，
> 已有 `assets/raw/` 会跳过、不重复花钱。见手册坑 ⑥。
> 若报 `HTTP 429 — API Key 额度不足`：`apiz account balance` 有钱也没用，
> 那是 **API Key 自带独立额度**用尽（串行也照样报，不是并发问题），
> 需到控制台提高/重置该 Key 额度。

`assets.json` 清单格式：

```json
{
  "defaults": { "quality":"low", "complexity":"low", "aspect_ratio":"1:1", "size":"1K" },
  "svg": [ { "name":"bulb-line", "prompt":"...clean native SVG vector paths..." } ],
  "gif": [ { "name":"bulb-pulse", "prompt":"...seamless loop...",
             "frame_count":9, "frame_duration_ms":200 } ]
}
```

常用参数：`--only <name>` 只做一个、`--force` 重抽（会再花钱）、`--dry-run` 只看计划。

---

## 4. 页面 API

```js
// 左：SVG 逐笔生长
P.vector('bulb-line', 190, 260, 540, 540, {
  at: P.c(0), dur: 2.6, mode: 'draw',   // 'draw' | 'fade' | 'instant'
  stagger: 0.55, fillDelay: 0.62,       // 路径错开、填充延后
  stroke: 'blue', sw: 3,                // 可选：只改显式描边色，不动 url(#gradient)
});

// 右：GIF 拆帧后的循环
P.clip('bulb-pulse', 1100, 260, 540, 540, {
  at: P.c(2), fps: 5, loop: true,       // 200ms/帧 → 5fps
  // 可用 pingpong / timeMap 对齐 P.cw(i,'词') / speed / from / to / start
});
```

`P.clip` 是引擎自带接口（`engine/runtime/media.js`），支持 `loop / pingpong / timeMap /
fps / speed / from / to / start`；`__frameReady(t)` 会等帧解码完再重绘，
渲染、拼图、单帧三条路都 await 它。

**可选手法，不是硬要求**：`pingpong` 能把 9 帧扩成 17 帧来回，缓解循环接缝；
`timeMap` 能把动效卡在念到某个词的瞬间；`stroke:'ink'` 能让 AI 素材更贴白板风格。
用不用、用多少，看画面，不写死。

---

## 5. 硬纪律（每条都有实测依据）

1. **素材生成要幂等** —— `assets/raw/` 已有就跳过，生成是抽卡且计费。
2. **先看终态单帧** —— 动画最后才出现的元素，拼图最后一帧可能还没长完（实测只有 76%）。
3. **lint 全绿 ≠ 画面对** —— 构图、遮挡、文字被色块盖住只有看图能发现。
4. **字幕带 y > 900 不放内容**，文字底 = y + 字号×1.45。
5. **换素材后不必手清 `out/chunks`** —— manifest 会改 digest；但绕过 `ftasset.py`
   手工换图就必须自己清缓存（引擎不 hash `assets/`）。
6. **组件方法叫 `P.vector()`，不能叫 `P.svg`** —— `Builder` 构造函数里
   `this.svg = s('svg', ...)` 是这一页的画布 SVG 元素，实例属性会遮蔽同名原型方法。
   实测症状：组件挂载成功、`PV.Builder.prototype.svg` 是 function，但 `P.svg` 是 object，
   页面 build 报「P.svg is not a function」。
7. **渲染长片用 `--workers 1`（已是默认值）** —— 引擎默认 12 个浏览器 worker，
   11 页以上会 OOM；2026-11-08 实测 12 workers 两次崩、1 worker 一次成。

---

## 6. 能做 / 不能做

**能**：知识科普、概念图解、流程推导、图标套组、产品结构图、四格分镜；五套风格；
横竖屏；中英配音；自动字幕；真实截图与 AI 素材混排；任意页单独重渲。

**不能**：整片 AI 生成画面（会丢掉零成本、可精修、风格统一）；写实照片级连续视频；
自动配乐；GIF 做不到长镜头或复杂运镜（最多 9 帧）；用 edit 接口精修已生成的 SVG/GIF。

> 判断信号：**这一页的 AI 素材如果没画出「手绘画不出的东西」，就不该用。**
> 这是上游 3D 融合整片复盘换来的教训——技术图语言 ≠ 讲解语言。
> 新题材建议先做一页样板给用户看，确认视觉融合度，再决定铺开多少页。

---

## 7. 文档索引（全部随包提供）

| 什么时候读 | 读哪份 |
|---|---|
| 安装 / 快速开始 / 成本 / 许可 | `README.md` |
| 第一次接素材 / 排错 | `references/vector-motion-guide.md`（完整实测、参数边界、8 个坑、已废规则清单、待实测项） |
| 画任何一页之前 | `references/page-api.md` |
| 定分镜 / 写口播 | `references/storyboard-method.md`、`references/script-format.md` |
| 选风格 / 配色 | `references/style-packs.md` |
| 配音报错 | `references/tts-backends.md` |
| 引擎 / 依赖报错 | `references/troubleshooting.md` |
| 第三方归属与许可 | `vendor/ATTRIBUTION.md` |

## 8. 依赖与许可

- **自有代码 MIT**（`LICENSE`）：本仓库的脚本、组件、文档。
- **渲染引擎 Frametell 0.7.2 = AGPL-3.0-only**（Sitor Team）：**不在仓库内**，
  `scripts/setup.py` 用 sparse checkout 从上游拉取、独立进程调用。
  ⚠ 不要把引擎源码拷进本仓库或闭源项目。详见 `vendor/ATTRIBUTION.md`。
- **可选付费依赖**：`apiz` CLI + `apiz/gpt-image-2.6-flare`，只有生成新素材时需要。
  实测单价：SVG ≈ ¥0.23、GIF ≈ ¥0.25；100 积分 = ¥1。11 页正片 21 个素材合计约 ¥2.75。
- **免费配音**：`edge-tts`（默认，无需 key）；`apiz` 是付费备选。
- Python：Pillow（拆帧）、标准库 urllib（不使用 requests）。

## 9. 已完成度（发布前实测）

| 验收项 | 结果 |
|---|---|
| 单页样板 `examples/sample` | 离线跑通，lint 0 错 0 提醒，终态单帧完整 |
| 11 页正片 `pencil-craft-2026` | 121.9s / 33 句 / 11 SVG + 10 GIF，用户确认风格兼容 |
| 确定性 | `ftdeterminism.mjs` 11/11 页 0.000% 差异 |
| 成片 | 1920×1080 / 24fps / H.264+AAC / 33 条字幕，ffmpeg 全解码无错 |
| 独立安装 | 从干净目录 clone + setup，不依赖任何本机既有路径（见 `README.md` 验收流程） |
