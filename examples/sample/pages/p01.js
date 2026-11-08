/* 单页样板：左边 P.vector 精致矢量逐笔生长，右边 P.clip 真实 9 帧循环微动效。
 * 纪律照旧：不用 Math.random / Date.now / CSS transition；时间一律 P.c(i)。 */
ENGINE.visual('p01', (P) => {
  const t0 = P.c(0), t1 = P.c(1), t2 = P.c(2);

  P.title('结构画出来，再让它动', { accent: 'blue' });

  // ── 左：AI 生成的原生 SVG，按 lt 逐笔长出（不是整张淡入） ──
  P.vector('bulb-line', 190, 260, 540, 540, {
    at: t0, dur: 2.6, mode: 'draw', stagger: 0.55, fillDelay: 0.62,
  });

  // ── 右：AI 生成的 GIF 已拆成帧序列，由 P.clip 按 lt 取帧 ──
  // 原生 200ms/帧 = 5fps；loop 让 9 帧在本页余下时间里循环。
  P.clip('bulb-pulse', 1100, 260, 540, 540, {
    at: t2, fps: 5, loop: true, r: 18,
  });

  // ── 中间：手绘箭头把「画出来」连到「动起来」，保持讲解语言 ──
  P.arrow(790, 530, 1050, 530, { at: t2 + 0.15, color: 'blue', sw: 3.5 });
  P.text('让它动', { x: 920, y: 452, w: 260, align: 'c', size: 34, color: 'blue', at: t2 + 0.2, mode: 'fade' });

  // ── 两个标签：文字仍由手绘 P.text 出，不交给 SVG（避免字体/术语风险） ──
  P.text('矢量图解 · 逐笔生长', { x: 460, y: 818, w: 520, align: 'c', size: 34, color: 'ink', at: t1, mode: 'fade' });
  P.text('局部微动效 · 9 帧循环', { x: 1370, y: 818, w: 560, align: 'c', size: 34, color: 'ink', at: t2 + 0.3, mode: 'fade' });

  // 一句落在画面上的实话，说明两种素材各自负责什么
  P.text('结构靠矢量，呼吸靠动图', { x: 960, y: 210, w: 900, align: 'c', size: 30, color: 'muted', at: t0 + 0.2, mode: 'fade' });
});
