#!/usr/bin/env python3
"""自绘 B 站播放量历史图：单面板，和 gen_combo_chart.py 同一套视觉规则。

用法:
  python3 gen_views_chart.py <owner/repo> <accent> <out.svg> [bg.jpg] [charlabel]

画布 800x700、同一张背景 + 白色蒙版、同一套字体/网格/平滑（PCHIP 单调插值）、
同样的 5 条横向网格 + 5 个横向刻度。

数据来源 .github/view-history/history.json：
  * backfill  —— 发布日到首个实测快照之前，双指数回推估算（虚线，55% 透明）
  * snapshots —— 每天实测（实线）
快照由 bilibili_views.py --snapshot 写入。
"""
import base64
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_combo_chart import (  # noqa: E402  同一套视觉工具，避免两份样式各写一遍
    GOLD,
    esc,
    img_size,
    nice_max,
    parse_t,
    smooth_path,
)

W, H = 800, 700
M_L, M_R = 60, 30
P_TOP, P_H = 100, 482
PLOT_W = W - M_L - M_R
X_LABEL_Y = P_TOP + P_H + 22
VIEW_HIST = ".github/view-history/history.json"


def comma(v):
    return "{:,}".format(int(round(v)))


def load_views(path=VIEW_HIST):
    """读播放量历史。backfill=回推估算（虚线），snapshots=每日实测（实线）。"""
    if not os.path.exists(path):
        return None
    try:
        h = json.load(open(path, encoding="utf-8"))
    except Exception:
        return None

    pts, first_real, n_snap = [], None, 0
    for e in h.get("backfill") or []:
        try:
            pts.append((datetime.datetime.fromisoformat(e["date"] + "T00:00:00+00:00"), int(e["view"])))
        except Exception:
            continue
    for s in h.get("snapshots") or []:
        try:
            t = parse_t(s["t"]) if s.get("t") else datetime.datetime.fromisoformat(s["date"] + "T00:00:00+00:00")
            pts.append((t, int(s["view"])))
        except Exception:
            continue
        n_snap += 1
        if first_real is None or t < first_real:
            first_real = t
    if not pts:
        return None
    pts.sort(key=lambda p: p[0])
    return {
        "pts": pts,
        "first_real": first_real,
        "cur": pts[-1][1],
        "n_snap": n_snap,
        "n_backfill": len(pts) - n_snap,
        "bvid": h.get("bvid", ""),
        "url": h.get("url", ""),
        "title": h.get("title", ""),
        "pub": parse_t(h["pubdate"]) if h.get("pubdate") else None,
    }


def gen(repo, accent, views, now, bg_path=None, charlabel="", gold=GOLD):
    pts = list(views.get("pts") or [])
    cur = views.get("cur") or 0
    vmax = nice_max(cur)
    first_real = views.get("first_real")
    pub = views.get("pub")
    title = views.get("title") or ""
    bvid = views.get("bvid") or ""

    t0 = pts[0][0] if pts else now
    t1 = max(now, pts[-1][0]) if pts else now
    span = max((t1 - t0).total_seconds(), 1)

    def X(dt):
        return M_L + (dt - t0).total_seconds() / span * PLOT_W

    def Y(v):
        return P_TOP + P_H - min(v, vmax) / vmax * P_H

    split = X(first_real) if (pts and first_real and t0 < first_real < t1) else None

    d, area = "", ""
    if pts:
        d = smooth_path([(X(dt), Y(v)) for dt, v in pts])
        area = d + " L %.1f,%.1f L %.1f,%.1f Z" % (X(pts[-1][0]), P_TOP + P_H, X(pts[0][0]), P_TOP + P_H)

    bg = ""
    if bg_path and os.path.exists(bg_path):
        b64 = base64.b64encode(open(bg_path, "rb").read()).decode()
        size = img_size(bg_path)
        if size:
            iw, ih = size
            scale = max(W / iw, H / ih)
            dw, dh = iw * scale, ih * scale
            ox, oy = (W - dw) / 2.0, (H - dh) / 2.0
        else:
            dw, dh, ox, oy = W, H, 0, 0
        bg = ('<image x="%.2f" y="%.2f" width="%.2f" height="%.2f" '
              'href="data:image/jpeg;base64,%s"/>' % (ox, oy, dw, dh, b64))

    grid, ylab = [], []
    for i in range(5):
        v = vmax * i / 4
        y = Y(v)
        grid.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#8f86ad" stroke-opacity="0.26" stroke-width="1"/>'
                    % (M_L, y, W - M_R, y))
        dy = -6 if i == 0 else (13 if i == 4 else 4)
        ylab.append('<text x="%.1f" y="%.1f" text-anchor="end" class="ax">%s</text>'
                    % (M_L - 8, y + dy, comma(v)))

    xticks, xlabels = [], []
    for i in range(5):
        tt = t0 + datetime.timedelta(seconds=span * i / 4)
        x = X(tt)
        xticks.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#8f86ad" stroke-opacity="0.26" stroke-width="1"/>'
                      % (x, P_TOP, x, P_TOP + P_H))
        anchor = "start" if i == 0 else ("end" if i == 4 else "middle")
        lx = M_L if i == 0 else (W - M_R if i == 4 else x)
        xlabels.append('<text x="%.1f" y="%.1f" text-anchor="%s" class="ax">%s</text>'
                       % (lx, X_LABEL_Y, anchor, tt.strftime("%m-%d")))

    # 发布竖线：只有发布时间明显落在图内才画（否则它就和左轴重合了）
    pub_line, pub_mark = "", ""
    px = X(pub) if pub else None
    if px is not None and M_L + 24 < px < W - M_R - 8:
        pub_line = ('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                    'stroke-opacity="0.55" stroke-width="1.1" stroke-dasharray="4 4"/>'
                    % (px, P_TOP, px, P_TOP + P_H, gold))
        pub_mark = ('<text x="%.1f" y="%.1f" text-anchor="start" class="rel">B站发布 %s</text>'
                    % (px + 4, P_TOP + P_H - 8, pub.strftime("%Y-%m-%d")))

    ex = X(pts[-1][0]) if pts else M_L
    ey = Y(cur) if pts else P_TOP + P_H

    short_title = title if len(title) <= 20 else title[:20] + "…"
    bits = [b for b in (charlabel, short_title) if b]
    bits.append("%s 播放" % comma(cur))
    if pts:
        bits.append("%s → %s" % (t0.strftime("%Y-%m-%d"), t1.strftime("%Y-%m-%d")))
    sub = " · ".join(bits)

    n_snap = views.get("n_snap") or 0
    n_back = views.get("n_backfill") or 0
    foot = ("Source: Bilibili x/web-interface/view · 每日自动快照 · %d 个实测快照" % n_snap
            + ("（更早 %d 天为回推估算，虚线）" % n_back if n_back else ""))

    head = "▶ %s · 播放量 History" % repo

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
  <title id="t">{esc(head)}</title>
  <desc id="d">{esc(title)} — {comma(cur)} views on Bilibili{(", published %s" % pub.date()) if pub else ""}</desc>
  <defs>
    <linearGradient id="fillView" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.30"/>
      <stop offset="100%" stop-color="{accent}" stop-opacity="0.02"/>
    </linearGradient>
    <linearGradient id="veil" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.88"/>
      <stop offset="22%" stop-color="#ffffff" stop-opacity="0.30"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0.26"/>
    </linearGradient>
    <clipPath id="vEst"><rect x="0" y="0" width="{split or 0:.1f}" height="{H}"/></clipPath>
    <clipPath id="vReal"><rect x="{split or 0:.1f}" y="0" width="{W - (split or 0):.1f}" height="{H}"/></clipPath>
  </defs>
  <rect width="{W}" height="{H}" fill="#f7f5fb"/>
  {bg}
  <rect width="{W}" height="{H}" fill="url(#veil)"/>
  <style>
    .ttl{{font:700 17px -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;fill:#2b2440;stroke:#ffffff;stroke-opacity:0.92;stroke-width:3.4;paint-order:stroke fill}}
    .sub{{font:400 12.5px -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;fill:#514a66;stroke:#ffffff;stroke-opacity:0.88;stroke-width:2.8;paint-order:stroke fill}}
    .pt{{font:700 12.5px -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;fill:#3b3355;stroke:#ffffff;stroke-opacity:0.9;stroke-width:3;paint-order:stroke fill}}
    .ax{{font:400 11.5px -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;fill:#4f4864;stroke:#ffffff;stroke-opacity:0.85;stroke-width:2.6;paint-order:stroke fill}}
    .val{{font:700 13px -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;fill="{accent}";stroke:#ffffff;stroke-opacity:0.9;stroke-width:2.8;paint-order:stroke fill}}
    .rel{{font:400 10.5px ui-monospace,SFMono-Regular,Menlo,monospace;fill:{gold}}}
  </style>
  <text x="{M_L}" y="30" class="ttl">{esc(head)}</text>
  <text x="{M_L}" y="50" class="sub">{esc(sub)}</text>
  {''.join(grid)}
  {''.join(xticks)}
  <text x="{M_L + 8}" y="{P_TOP + 16}" class="pt">▶ 播放量 History</text>
  {''.join(ylab)}
  {''.join(xlabels)}
  {pub_line}
  <path d="{area}" fill="url(#fillView)"/>
  <path d="{d}" fill="none" stroke="#ffffff" stroke-opacity="0.72" stroke-width="5" stroke-linejoin="round" stroke-linecap="round" stroke-dasharray="5 4" clip-path="url(#vEst)"/>
  <path d="{d}" fill="none" stroke="#ffffff" stroke-opacity="0.72" stroke-width="5" stroke-linejoin="round" stroke-linecap="round" clip-path="url(#vReal)"/>
  <path d="{d}" fill="none" stroke="{accent}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" stroke-opacity="0.55" stroke-dasharray="5 4" clip-path="url(#vEst)"/>
  <path d="{d}" fill="none" stroke="{accent}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" clip-path="url(#vReal)"/>
  {pub_mark}
  <circle cx="{ex:.1f}" cy="{ey:.1f}" r="4.2" fill="{accent}" stroke="#ffffff" stroke-width="2"/>
  <text x="{min(ex - 6, W - M_R - 6):.1f}" y="{ey - 10:.1f}" text-anchor="end" class="val">▶ {comma(cur)}</text>
  <text x="{W - M_R}" y="{P_TOP + P_H - 8}" text-anchor="end" class="ax">B站 {esc(bvid)}</text>
  <text x="{M_L}" y="{H - 14}" class="ax">{esc(foot)}</text>
</svg>
'''


if __name__ == "__main__":
    args = sys.argv[1:]
    repo = args[0] if args else "alsunmengy/DeepSeek-PCB-Art"
    accent = args[1] if len(args) > 1 else "#4D6BFE"
    out = args[2] if len(args) > 2 else ".github/charts/views.svg"
    bgp = args[3] if len(args) > 3 and args[3] else ".github/star-history/bg.jpg"
    charlabel = args[4] if len(args) > 4 else "DeepSeek 人鱼少女"
    if not os.path.exists(bgp):            # 参数位被跳过/传错时，退回默认背景
        bgp = ".github/star-history/bg.jpg"

    views = load_views()
    if not views:
        print("[error] 没有 .github/view-history/history.json，先跑 bilibili_views.py --bootstrap --snapshot",
              file=sys.stderr)
        sys.exit(1)

    now = datetime.datetime.now(datetime.timezone.utc)
    svg = gen(repo, accent, views, now, bgp if os.path.exists(bgp) else None, charlabel)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    open(out, "w", encoding="utf-8").write(svg)
    print("views %s (%d snapshots, %d backfill) -> %s, %d bytes"
          % (comma(views["cur"]), views["n_snap"], views["n_backfill"], out, len(svg.encode())))
