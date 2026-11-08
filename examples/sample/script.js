/* 矢量动效样板 —— 单页，验证 P.vector 逐笔生长 + P.clip 局部微动效 与手绘版面的融合度。
 * 素材在 assets/raw/ 里随包提供，ftasset.py 会复用它们、不调用任何付费 API。 */
(function (root) {
  const META = {
    voice: { speaker: 'zh-CN-XiaoxiaoNeural' },
    style: 'whiteboard',
    title: '矢量动效样板',
    name: '矢量动效样板',
    gap: 0.5,
    // 顺序不能反：素材数据 → 帧数注册 → 缓存哈希 → 组件（组件要读到 SVG_ASSETS）
    extras: [
      'extras/svg-assets.js',
      'extras/clips.js',
      'extras/asset-manifest.js',
      'extras/motion-svg.js',
    ],
  };
  const PAGES = [
    { id: 'p01', section: '样板', title: '结构画出来，再让它动', cues: [
      '先看清它的结构。',
      '一根线一根线，把灯泡画出来。',
      { t: '然后让它真的亮起来。', hold: 1.4 },
    ] },
  ];
  root.SCRIPT = { META, PAGES };
})(typeof window !== 'undefined' ? window : globalThis);
