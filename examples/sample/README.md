# 离线单页样板

这个目录是一个**完整的项目输入**，只差引擎链接。素材已经放在 `assets/raw/` 里，
所以整条流水线不需要 `apiz`、不需要 API key、不产生任何费用。

```
index.html             引擎入口（相对引用 engine/ 与 engine_modules/）
script.js              1 页 3 句口播 + META.extras 四项
pages/p01.js           P.vector 逐笔生长 + P.clip 帧序列 + 手绘文字/箭头
assets.json            素材清单（名称与页面里的引用一致）
assets/raw/            1 个 SVG + 1 个 GIF（原始下载，断点续用）
```

## 跑法

`<skill>` = 仓库根目录。项目必须放在 **skill 目录之外**（`ftnew.py` 会建
`engine` / `engine_modules` 链接，放在里面会形成目录环）。

```bash
cp -r examples/sample <项目>
python <skill>/scripts/ftnew.py <项目> --title "矢量动效样板" --style whiteboard
python <skill>/scripts/ftasset.py <项目> --spec <项目>/assets.json
python <skill>/scripts/ftvoice.py <项目>
python <skill>/scripts/ftcheck.py <项目>
cd <项目> && node <skill>/scripts/ftdeterminism.mjs
cd <skill> && python <skill>/scripts/ftrender.py <项目> --fps 24
```

`ftnew.py` 看到已有 `script.js` 会保留现有内容，只补两个链接，所以顺序是
**先复制、再 ftnew**。

`ftasset.py` 会打印两条「复用已有」，并生成：

```
assets/svg/bulb-line.svg          清洗后的 SVG
assets/clips/bulb-pulse/f000.jpg…  GIF 拆出的 9 帧
extras/*.js                       内联素材、帧数、哈希、P.vector 组件
```

预期结果：单页约 9.3 秒，lint 0 错 0 提醒，成片在 `<项目>/out/`。

## 想换成自己的素材

编辑 `assets.json` 的 `prompt`，删掉 `assets/raw/` 里对应文件（或加 `--force`），
再跑 `ftasset.py`。这一步才会调用付费 API。名称要和 `pages/p01.js` 里的
`P.vector('bulb-line', …)` / `P.clip('bulb-pulse', …)` 保持一致。
