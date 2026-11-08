/* motion-svg.js · 时间驱动的原生 SVG 组件（项目级 extras）
 *
 * 由 ftasset.py 连同 `extras/svg-assets.js` 一起装进项目。
 * SVG_ASSETS 把清洗过的 SVG 源码同步内联进来，所以页面 build 阶段不需要 fetch，
 * 这让 renderAt(t) 保持「时间的纯函数」：分段缓存、确定性校验、任意跳转都还在。
 *
 *   P.vector(name, x, y, w, h, {
 *     at, dur, mode:'draw'|'fade'|'instant', stagger, fillDelay,
 *     stroke:'blue', sw:3, fit:'xMidYMid meet'
 *   }) → { el, svg, hide(t,d), count }
 *
 * ★ 为什么叫 vector 而不是 svg：Builder 构造函数里有 `this.svg = s('svg', ...)`，
 *   实例属性 `svg` 是这一页的画布 SVG 元素，会遮蔽 prototype 上的同名方法。
 *   实测症状：挂载成功（PV.Builder.prototype.svg 是 function），但 P.svg 是 object，
 *   页面 build 直接报「P.svg is not a function」。
 *
 * 红线：只用 P.tick 给的 lt。禁止 Date.now / Math.random / CSS transition / rAF /
 * SMIL <animate>。ftasset.py 已在落盘前把这些从 SVG 里剥掉。
 */
(function () {
  // Builder 只挂在 PV 上（core.js 的 IIFE 局部变量），不是全局标识符。
  // 写成裸 `Builder.prototype` 会在加载阶段就 ReferenceError，页面只会报「P.svg is not a function」。
  const { h, clamp, ease, col, Builder } = PV;
  const B = Builder.prototype;
  const ASSETS = window.SVG_ASSETS || {};
  const GEOM = 'path,line,polyline,polygon,circle,ellipse,rect';

  B.vector = function (name, x, y, w, hh, o = {}) {
    const raw = ASSETS[name];
    if (!raw) { console.error('svg asset missing: ' + name + ' (run ftasset.py)'); return null; }

    const el = h('div', 'motion-svg', null, this.html);
    Object.assign(el.style, {
      position: 'absolute', left: x + 'px', top: y + 'px',
      width: w + 'px', height: hh + 'px', overflow: 'hidden', opacity: '1',
    });

    const doc = new DOMParser().parseFromString(raw, 'image/svg+xml');
    const root = doc.documentElement;
    if (!root || root.nodeName.toLowerCase() !== 'svg') {
      console.error('svg asset is not an <svg>: ' + name);
      return null;
    }
    const svg = document.importNode(root, true);
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', '100%');
    svg.setAttribute('preserveAspectRatio', o.fit || 'xMidYMid meet');
    svg.style.display = 'block';
    svg.style.width = '100%';
    svg.style.height = '100%';
    el.appendChild(svg);

    // defs 里的几何是渐变/图案的定义，不是要画的图形，跳过。
    const items = [...svg.querySelectorAll(GEOM)].filter((n) => !n.closest('defs')).map((n) => {
      const f = (n.getAttribute('fill') || '').trim();
      return { n, len: 0, filled: f !== '' && f.toLowerCase() !== 'none' };
    });

    // 可选：把显式描边统一换成风格包语义色。url(#gradient) 一律不动，免得把渐变弄丢。
    if (o.stroke) {
      const c = col(o.stroke);
      for (const it of items) {
        const s = it.n.getAttribute('stroke');
        if (s && s.trim() && s.indexOf('url(') === -1) it.n.setAttribute('stroke', c);
      }
    }
    if (o.sw != null) {
      for (const it of items) if (it.n.hasAttribute('stroke')) it.n.setAttribute('stroke-width', String(o.sw));
    }

    const at = o.at ?? 0;
    const dur = o.dur ?? 1.2;
    const mode = o.mode || 'draw';
    const stagger = clamp(o.stagger ?? 0.35, 0, 0.9);
    const fillDelay = clamp(o.fillDelay ?? 0.6, 0, 0.95);
    const span = Math.max(0.2, dur * (1 - stagger));
    let measured = false, outAt = null, outDur = 0.5;

    // 长度测量与 lt 无关，只做一次；失败就退化为淡入，绝不产生 NaN。
    function measure() {
      if (measured) return;
      for (const it of items) {
        let L = 0;
        try { L = it.n.getTotalLength(); } catch (e) { L = 0; }
        if (!isFinite(L) || L < 1) L = 0;
        it.len = L;
        if (mode === 'draw' && L > 0) {
          it.n.style.strokeDasharray = L + ' ' + L;
          it.n.style.strokeDashoffset = String(L);
        }
        if (mode === 'draw' && it.filled) it.n.style.fillOpacity = '0';
      }
      measured = true;
    }

    this.tick((lt) => {
      measure();
      const vis = outAt == null ? 1 : 1 - clamp((lt - outAt) / outDur);
      if (mode === 'draw') {
        const N = items.length;
        for (let i = 0; i < N; i++) {
          const a = at + dur * stagger * (N > 1 ? i / (N - 1) : 0);
          const k = clamp((lt - a) / span);
          const e = ease.inOut(k);
          const it = items[i];
          if (it.len > 0) it.n.style.strokeDashoffset = (it.len * (1 - e)).toFixed(2);
          if (it.filled) it.n.style.fillOpacity = clamp((k - fillDelay) / (1 - fillDelay)).toFixed(3);
        }
        el.style.opacity = (clamp((lt - at) / 0.25) * vis).toFixed(3);
      } else if (mode === 'fade') {
        el.style.opacity = (clamp((lt - at) / dur) * vis).toFixed(3);
      } else {
        el.style.opacity = vis.toFixed(3);
      }
    });

    return {
      el, svg,
      hide(t, d = 0.5) { outAt = t; outDur = d; return this; },
      get count() { return items.length; },
    };
  };
})();
