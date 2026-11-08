"""为 frametell 项目生成「精致矢量图解 + 局部真实微动效」素材，并把它们接进时间轴。

用法
----
  python ftasset.py <项目目录> --spec <项目目录>/assets.json [--only name] [--force] [--dry-run]

spec 格式（一个素材一条，name 就是页面里 P.vector / P.clip 用的名字）：
{
  "defaults": { "quality":"low", "complexity":"low", "aspect_ratio":"1:1", "size":"1K" },
  "svg": [ { "name":"bulb", "prompt":"...output SVG..." } ],
  "gif": [ { "name":"bulb-glow", "prompt":"...seamless loop...", "frame_count":9,
             "frame_duration_ms":200 } ]
}

产出
----
  assets/raw/<name>.svg|.gif       原始下载（便于复核 / 断点续用）
  assets/svg/<name>.svg            清洗后的 SVG（剥掉脚本、SMIL、外链、文字）
  assets/clips/<name>/f000.jpg…   GIF 拆出的帧序列，直接喂 P.clip
  extras/svg-assets.js            window.SVG_ASSETS —— 同步内联，页面不 fetch
  extras/clips.js                 window.CLIP_FRAMES —— 帧数注册（等价于 clips.mjs）
  extras/asset-manifest.js        素材哈希 —— 让渲染缓存 digest 感知素材变化

★ 为什么 manifest 必须存在：engine/tools/render.mjs 的分段缓存只 hash
  extras/ / index.html / META / pages/*.js，**不 hash assets/**。素材重新生成而
  文件名不变时，若没有 extras 里的哈希，画面不会重渲（静默用旧帧）。

设计取舍
--------
- 用 apiz CLI（subprocess list 传参，避开 Windows shell 引号问题），不写 requests。
- 已有 assets/raw/<name>.* 就跳过调用：生成是抽卡且要花钱，必须幂等。
  --force 才重抽。
- 素材一旦落盘，渲染仍是完全确定的：不确定的只有「生成」这一步。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

MODEL = "apiz/gpt-image-2.6-flare"
SVGNS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVGNS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

# 这些标签要么会自己跑动画，要么带外部资源/文字，进 renderAt(t) 纯函数一律不安全。
DANGER_TAGS = {
    "script", "animate", "animatetransform", "animatemotion", "animatecolor",
    "set", "discard", "image", "foreignobject", "style", "text", "tspan",
    "textpath", "a", "audio", "video", "iframe", "handler", "use",
}
EXTERNAL = re.compile(r"https?://", re.I)
ANIM_DECL = re.compile(r"animation|transition|@keyframes", re.I)

# AI 生成 SVG 偶尔把「没求值的算式」或英文单词写进数值属性，浏览器会直接丢弃该图形
# 且只在 console 报一句 Expected length / Expected number，画面上静默缺笔。
# 2026-11-08 实测：hb-scale.svg 六条刻度线写成 x1="132+142.857…"、
# hex-profile.svg 一条 path 写成 d="M140 580 C100 540 70 520  eighty 480"。见手册坑 ⑦。
GEOM_ATTRS = {"x", "y", "x1", "x2", "y1", "y2", "cx", "cy", "r", "rx", "ry", "width", "height"}
PATH_CMD = set("mlhvcstqazMLHVCSQTAZ")
NUM_RE = re.compile(r"[+-]?(?:\d*\.?\d+)(?:[eE][+-]?\d+)?")


def fix_geom_value(v: str):
    """'132+142.857…' → '274.857'。只处理纯加法算式，其余一律不乱改。"""
    if re.fullmatch(r"\s*-?[\d.]+\s*(?:\+\s*-?[\d.]+\s*)+", v):
        try:
            return "%g" % sum(float(x) for x in v.split("+"))
        except ValueError:
            return None
    return None


def path_has_junk(d: str) -> bool:
    """d 去掉数字后剩下的字母若含非路径命令（如 'eighty'），浏览器无法解析。"""
    return any(c.isalpha() and c not in PATH_CMD for c in NUM_RE.sub("", d))


class AssetError(RuntimeError):
    """可预期错误：消息直接给用户看，不打堆栈。"""


def find_apiz() -> str:
    exe = shutil.which("apiz")
    if exe:
        return exe
    for cand in (Path.home() / ".local" / "bin" / "apiz.exe",
                 Path.home() / ".local" / "bin" / "apiz"):
        if cand.exists():
            return str(cand)
    raise AssetError(
        "找不到 apiz CLI（只有生成新素材时才需要）。\n"
        "安装与配置见本仓库 README 的「安装」章节；复用 examples/ 自带素材不需要它"
    )


def find_engine(project: Path | None = None) -> Path | None:
    """找渲染引擎：FRAMETELL_ENGINE → 项目里的 engine 链接 → 本 skill 的 engine/。

    素材生成（下载 / 清洗 / 拆帧 / 写 extras）本身不需要引擎，所以这里只探测、
    不阻断；渲染前由 setup.py 保证引擎就位。
    """
    env = os.environ.get("FRAMETELL_ENGINE")
    cands: list[Path] = []
    if env:
        cands.append(Path(env))
    if project:
        cands.append(project / "engine")
    cands.append(Path(__file__).resolve().parent.parent / "engine")
    for p in cands:
        if (p / "tools" / "render.mjs").exists():
            return p
    return None


def apiz_call(args: list[str], timeout: int = 600) -> dict:
    p = subprocess.run([find_apiz(), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    if p.returncode:
        raise AssetError(f"apiz 调用失败（{p.returncode}）：\n{(p.stderr or p.stdout).strip()[:800]}")
    out = (p.stdout or "").strip()
    i = out.find("{")
    if i < 0:
        raise AssetError(f"apiz 返回的不是 JSON：{out[:400]}")
    try:
        return json.loads(out[i:])
    except json.JSONDecodeError as e:
        raise AssetError(f"apiz 返回 JSON 解析失败：{e}\n{out[:400]}")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def sanitize_svg(raw: str) -> str:
    """剥掉会破坏「时间纯函数」的东西，保留 viewBox / defs 渐变 / 几何路径。"""
    raw = re.sub(r"<!DOCTYPE[^>]*>", "", raw, flags=re.I)
    raw = re.sub(r"<\?xml[^>]*\?>", "", raw, flags=re.I)
    root = ET.fromstring(raw.strip())

    fixed = dropped = 0

    def walk(el):
        nonlocal fixed, dropped
        for ch in list(el):
            tag = ch.tag.split("}")[-1].lower()
            if tag in DANGER_TAGS:
                el.remove(ch)
                continue
            junk = False
            for k in list(ch.attrib):
                lk = k.split("}")[-1].lower()
                v = ch.attrib[k]
                if lk.startswith("on") or lk in {"href", "src"}:
                    del ch.attrib[k]
                    continue
                if EXTERNAL.search(v):
                    del ch.attrib[k]          # 外部 url()/字体引用一律降级
                    continue
                if lk == "style":
                    keep = [d for d in v.split(";") if not ANIM_DECL.search(d)]
                    ch.attrib[k] = ";".join(keep)
                    continue
                if lk in GEOM_ATTRS:
                    f = fix_geom_value(v)
                    if f is not None:
                        ch.attrib[k] = f
                        fixed += 1
                if lk == "d" and path_has_junk(v):
                    junk = True               # 无法解析的路径：整条剔除，避免半截图形
                    break
            if junk:
                el.remove(ch)
                dropped += 1
                continue
            walk(ch)

    walk(root)
    if fixed or dropped:
        print(f"  ⚠ SVG 数值修复：{fixed} 个未求值算式已求值、{dropped} 条无法解析路径已剔除")
    w, hgt = root.attrib.get("width"), root.attrib.get("height")
    for k in list(root.attrib):
        lk = k.split("}")[-1].lower()
        if lk.startswith("on") or lk in {"width", "height"}:
            del root.attrib[k]
    root.set("width", "100%")
    root.set("height", "100%")
    if "viewBox" not in root.attrib:
        def num(s):
            m = re.match(r"\s*([\d.]+)", s or "")
            return m.group(1) if m else "1024"
        root.set("viewBox", f"0 0 {num(w)} {num(hgt)}")
    return ET.tostring(root, encoding="unicode")


def gif_to_frames(data: bytes, outdir: Path) -> dict:
    from PIL import Image
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("f*.jpg"):
        old.unlink()                       # 避免旧帧残留导致 CLIP_FRAMES 数错
    im = Image.open(io.BytesIO(data))
    n = getattr(im, "n_frames", 1)
    durations = []
    for i in range(n):
        im.seek(i)
        durations.append(im.info.get("duration", 0))
        im.convert("RGB").save(outdir / f"f{i:03d}.jpg", quality=92, subsampling=0)
    return {"frames": n, "size": list(im.size), "durations": durations}


def js_const(file: Path, var: str, obj: dict, note: str) -> None:
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    # 防 </script> 提前闭合；JS 解析时 \u003c 会还原成 <
    s = s.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(f"/* {note} */\nwindow.{var} = {s};\n", encoding="utf-8")


def write_extras(project: Path) -> dict:
    extras = project / "extras"
    svg_map = {}
    for f in sorted((project / "assets" / "svg").glob("*.svg")):
        svg_map[f.stem] = f.read_text(encoding="utf-8")

    clip_dir = project / "assets" / "clips"
    clip_frames = {}
    if clip_dir.exists():
        for d in sorted(p for p in clip_dir.iterdir() if p.is_dir()):
            n = len(list(d.glob("f[0-9][0-9][0-9].jpg")))
            if n:
                clip_frames[d.name] = n

    h = hashlib.sha256()
    for name in sorted(svg_map):
        h.update(name.encode() + svg_map[name].encode("utf-8"))
    for name in sorted(clip_frames):
        for f in sorted((clip_dir / name).glob("f*.jpg")):
            h.update(name.encode() + f.read_bytes())
    manifest = {
        "digest": h.hexdigest()[:16],
        "model": MODEL,
        "svg": sorted(svg_map),
        "gif": {k: v for k, v in sorted(clip_frames.items())},
    }

    js_const(extras / "svg-assets.js", "SVG_ASSETS", svg_map,
             "generated by ftasset.py · cleaned inline SVG, no fetch at build time")
    js_const(extras / "clips.js", "CLIP_FRAMES", clip_frames,
             "generated by ftasset.py · frame counts for P.clip (equals engine/tools/clips.mjs)")
    js_const(extras / "asset-manifest.js", "ASSET_MANIFEST", manifest,
             "generated by ftasset.py · asset hashes so render cache notices asset changes")

    # 组件自动安装：漏掉这一步的症状是「P.svg is not a function」，很难联想到素材脚本。
    lib = Path(__file__).resolve().parent.parent / "lib" / "motion-svg.js"
    if lib.exists():
        shutil.copyfile(lib, extras / "motion-svg.js")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="生成矢量/动图素材并接入 frametell 时间轴")
    ap.add_argument("project")
    ap.add_argument("--spec", default=None, help="素材清单 JSON，默认 <项目>/assets.json")
    ap.add_argument("--only", default=None, help="只处理某个 name")
    ap.add_argument("--force", action="store_true", help="忽略已有素材，重新调用 API（会再花钱）")
    ap.add_argument("--dry-run", action="store_true", help="只打印要生成什么，不调用 API")
    args = ap.parse_args()

    project = Path(args.project).resolve()
    if not (project / "script.js").exists():
        raise AssetError(
            f"不是 frametell 项目（缺 script.js）：{project}\n"
            '先运行 python scripts/ftnew.py <项目> --title "..." --style whiteboard'
        )
    if find_engine(project) is None:
        print("· 渲染引擎尚未安装（不影响素材生成）；渲染前运行 python scripts/setup.py")
    spec_path = Path(args.spec).resolve() if args.spec else project / "assets.json"
    if not spec_path.exists():
        raise AssetError(f"缺素材清单：{spec_path}")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    defaults = spec.get("defaults", {})
    jobs = ([(e, "svg") for e in spec.get("svg", [])] +
            [(e, "gif") for e in spec.get("gif", [])])
    if args.only:
        jobs = [(e, k) for e, k in jobs if e.get("name") == args.only]
    if not jobs:
        raise AssetError("素材清单里没有匹配的条目")

    raw_dir = project / "assets" / "raw"
    total = 0
    for entry, kind in jobs:
        name = entry.get("name")
        if not name or not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise AssetError(f"素材 name 只能用字母/数字/下划线/连字符：{name!r}")
        prompt = entry.get("prompt")
        if not prompt:
            raise AssetError(f"素材 {name} 缺 prompt")
        ext = "svg" if kind == "svg" else "gif"
        raw_file = raw_dir / f"{name}.{ext}"

        params = {k: v for k, v in defaults.items()}
        params.update({k: v for k, v in entry.items() if k not in {"name", "prompt"}})
        params["output_format"] = kind

        if raw_file.exists() and not args.force:
            print(f"· 复用已有 {name}.{ext}（要重抽加 --force）")
            data = raw_file.read_bytes()
            price = 0
        elif args.dry_run:
            print(f"[dry-run] 将生成 {name}.{ext}  params={json.dumps(params, ensure_ascii=False)}")
            continue
        else:
            print(f"→ 生成 {name}.{ext} …", flush=True)
            res = apiz_call([
                "generate", prompt, "--model", MODEL,
                "--params", json.dumps(params, ensure_ascii=False),
                "--wait", "--wait-timeout", "6m", "--json",
            ])
            if res.get("status") not in ("completed", "success"):
                raise AssetError(f"{name} 任务未成功：{res.get('status')} {res.get('error', '')}")
            images = ((res.get("result") or {}).get("images") or [])
            if not images or not images[0].get("url"):
                raise AssetError(f"{name} 返回里没有图片 URL：{json.dumps(res, ensure_ascii=False)[:500]}")
            price = res.get("price", 0)
            total += price
            data = fetch(images[0]["url"])
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_file.write_bytes(data)
            print(f"  ✓ {len(data)} bytes · {price} 积分 (¥{price / 100:.2f})")

        if kind == "svg":
            out = project / "assets" / "svg" / f"{name}.svg"
            out.parent.mkdir(parents=True, exist_ok=True)
            try:
                cleaned = sanitize_svg(data.decode("utf-8"))
            except Exception as e:
                raise AssetError(f"{name}.svg 清洗失败：{e}")
            out.write_text(cleaned, encoding="utf-8")
            print(f"  ✓ SVG 已清洗 → {out.relative_to(project)}  ({len(cleaned)} chars)")
        else:
            info = gif_to_frames(data, project / "assets" / "clips" / name)
            print(f"  ✓ 拆出 {info['frames']} 帧 {info['size'][0]}×{info['size'][1]} "
                  f"· 帧时长 {info['durations']} → assets/clips/{name}/")

    if args.dry_run:
        print("[dry-run] 未调用 API、未写文件")
        return 0

    m = write_extras(project)
    need = ["extras/svg-assets.js", "extras/clips.js",
            "extras/asset-manifest.js", "extras/motion-svg.js"]
    script_txt = (project / "script.js").read_text(encoding="utf-8")
    missing = [n for n in need if n not in script_txt]
    warn = ""
    if missing:
        warn = ("\n⚠ script.js 的 META.extras 缺少：" + ", ".join(missing) +
                "\n  extras: ['extras/svg-assets.js', 'extras/clips.js',\n"
                "           'extras/asset-manifest.js', 'extras/motion-svg.js']\n")

    print(f"""
✓ 素材就绪  digest={m['digest']}
  SVG  {', '.join(m['svg']) or '（无）'}
  GIF  {', '.join(f'{k}({v}帧)' for k, v in m['gif'].items()) or '（无）'}
  本次 API 花费 {total} 积分 (¥{total / 100:.2f})
  组件已自动装到 extras/motion-svg.js（在 extras 里，所以也会被缓存 digest hash）
{warn}  下一步：ftvoice.py → 写 pages/pNN.js → ftcheck.py
""")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssetError, subprocess.TimeoutExpired) as e:
        print(f"\n✗ {e}", file=sys.stderr)
        sys.exit(1)
