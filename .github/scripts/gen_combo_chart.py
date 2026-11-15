#!/usr/bin/env python3
"""自绘 GitHub 双面板历史图：上 Star、下 Release 下载（共用时间轴）。

用法:
  python3 gen_combo_chart.py <owner/repo> <accent> <out.svg> [bg.jpg] [charlabel] [--snapshot]

数据来源:
  * stargazers（starred_at，可完整回溯建仓至今）
  * releases / assets 的 download_count + created_at（累计值，GitHub 无历史序列）
  * .github/download-history/history.json：每天采集的累计快照，--snapshot 时写入
  * 首个快照之前的下载区间按 asset 创建时间回推（时间常数 ~6 天），与实测点连成一条线
"""
import base64
import datetime
import json
import math
import os
import subprocess
import sys

W, H = 800, 700
M_L, M_R = 60, 30
P1_TOP, P1_H = 100, 268          # star 面板
P2_TOP, P2_H = 412, 198          # download 面板
PLOT_W = W - M_L - M_R
X_LABEL_Y = P2_TOP + P2_H + 22
GOLD = "#B07E1E"
C_PROJ = "#5A3FA8"
DEFAULT_BG = ".github/star-history/bg.jpg"
HIST = ".github/download-history/history.json"


def gh(args):
    r = subprocess.run(["gh", "api"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("gh api %s failed (%d): %s" % (" ".join(args), r.returncode, r.stderr.strip()[:600]))
    return json.loads(r.stdout)


def parse_t(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def kind_of(name):
    low = name.lower()
    if low.endswith(".epro2"):
        return "proj"
    if "gerber" in low or low.endswith(".zip"):
        return "gerber"
    return "other"


def fetch(repo):
    meta = gh(["repos/" + repo])
    created = parse_t(meta["created_at"])

    stars, page = [], 1
    while True:
        batch = gh(["repos/%s/stargazers?per_page=100&page=%d" % (repo, page),
                    "-H", "Accept: application/vnd.github.star+json"])
        if not batch:
            break
        stars += [parse_t(s["starred_at"]) for s in batch]
        if len(batch) < 100:
            break
        page += 1
    stars.sort()

    rel, page = [], 1
    while True:
        batch = gh(["repos/%s/releases?per_page=100&page=%d" % (repo, page)])
        if not batch:
            break
        rel += batch
        if len(batch) < 100:
            break
        page += 1

    assets, releases = [], []
    for r in rel:
        if r.get("published_at"):
            releases.append({"tag": r["tag_name"], "at": parse_t(r["published_at"])})
        for a in r.get("assets", []):
            assets.append({
                "name": a["name"],
                "dl": a.get("download_count") or 0,
                "at": parse_t(a.get("created_at") or r.get("published_at")),
                "kind": kind_of(a["name"]),
            })
    releases.sort(key=lambda x: x["at"])
    return created, stars, releases, assets


def totals(assets):
    t = {"total": 0, "proj": 0, "gerber": 0, "other": 0}
    for a in assets:
        t["total"] += a["dl"]
        t[a["kind"]] += a["dl"]
    return t


def load_hist():
    if os.path.exists(HIST):
        try:
            return json.load(open(HIST, encoding="utf-8"))
        except Exception:
            pass
    return {"snapshots": []}


def save_snapshot(repo, assets, tstamp):
    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    hist = load_hist()
    tt = totals(assets)
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    snap = {"t": tstamp.isoformat().replace("+00:00", "Z"), "date": today,
            "total": tt["total"], "proj": tt["proj"], "gerber": tt["gerber"], "other": tt["other"]}
    snaps = [s for s in hist.get("snapshots", []) if s.get("date") != today]
    snaps.append(snap)
    snaps.sort(key=lambda s: s["t"])
    hist["repo"] = repo
    hist["snapshots"] = snaps
    json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return hist


def img_size(path):
    """读 JPEG 尺寸（不依赖 PIL，Action 上也能跑）。"""
    with open(path, "rb") as f:
        data = f.read()
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            h = int.from_bytes(data[i + 5:i + 7], "big")
            w = int.from_bytes(data[i + 7:i + 9], "big")
            return w, h
        seglen = int.from_bytes(data[i + 2:i + 4], "big")
        i += 2 + seglen
    return None


def pchip_slopes(xs, ys):
    """Fritsch–Carlson 单调三次插值的节点斜率：保证曲线单调、不过冲。"""
    n = len(xs)
    if n < 2:
        return [0.0] * n
    h = [max(xs[i + 1] - xs[i], 1e-6) for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    return m


def dedupe_x(pts, min_gap=0.8):
    out = []
    for p in pts:
        if out and p[0] - out[-1][0] < min_gap:
            out[-1] = p
        else:
            out.append(p)
    return out


def smooth_path(pts):
    """点列 → 平滑 cubic bezier 路径（d 字符串）。"""
    pts = dedupe_x(pts)
    if len(pts) < 2:
        return "M %.1f,%.1f" % pts[0] if pts else ""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    m = pchip_slopes(xs, ys)
    k = 1.0 / 3.0
    parts = ["M %.1f,%.1f" % (xs[0], ys[0])]
    for i in range(len(xs) - 1):
        h = xs[i + 1] - xs[i]
        c1x, c1y = xs[i] + h * k, ys[i] + m[i] * h * k
        c2x, c2y = xs[i + 1] - h * k, ys[i + 1] - m[i + 1] * h * k
        parts.append("C %.1f,%.1f %.1f,%.1f %.1f,%.1f"
                     % (c1x, c1y, c2x, c2y, xs[i + 1], ys[i + 1]))
    return " ".join(parts)


def smooth_accum(times, t0, t1, n=72, sigma=2.6):
    """累积计数曲线：均匀时间网格采样 + 高斯平滑（保单调、去台阶感）。"""
    import bisect
    span = max((t1 - t0).total_seconds(), 1)
    ts = [t0 + datetime.timedelta(seconds=span * i / (n - 1)) for i in range(n)]
    vals = [float(bisect.bisect_right(times, t)) for t in ts]
    r = max(1, int(3 * sigma))
    kern = [math.exp(-0.5 * (k / sigma) ** 2) for k in range(-r, r + 1)]
    s = sum(kern)
    kern = [k / s for k in kern]
    out = []
    for i in range(n):
        acc = 0.0
        for j, k in enumerate(kern):
            acc += vals[min(max(i + j - r, 0), n - 1)] * k
        out.append((ts[i], acc))
    return out


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def nice_max(v):
    if v <= 0:
        return 4
    need = math.ceil(v / 4)
    k = 10 ** max(0, len(str(need)) - 1)
    for m in (1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if m * k >= need:
            return int(round(m * k)) * 4
    return need * 4


def build_dl_curve(assets, snaps, t0, t1, cur_total, n=96):
    """首个快照前按发布锚点回推，之后按真实快照连线，末点接当前值。"""
    tau = 6 * 86400.0
    acc = 0.0
    for a in assets:
        life = max((t1 - a["at"]).total_seconds(), 1)
        acc += a["dl"] / max(1 - math.exp(-life / tau), 1e-9)

    def raw(tt):
        v = 0.0
        for a in assets:
            if tt <= a["at"]:
                continue
            v += a["dl"] * (1 - math.exp(-(tt - a["at"]).total_seconds() / tau))
        return v

    pts = []
    if snaps:
        at = parse_t(snaps[0]["t"])
        if at <= t0:
            at = t0 + datetime.timedelta(seconds=1)
        base = raw(at)
        k = (snaps[0]["total"] / base) if base > 1e-9 else 0.0
        half = n // 2
        for i in range(half):
            tt = t0 + (at - t0) * (i / max(half - 1, 1))
            pts.append((tt, raw(tt) * k))
        for s in snaps:
            st = parse_t(s["t"])
            if st > t0:
                pts.append((st, s["total"]))
        if pts:
            pts.append((t1, cur_total))
        pts.sort(key=lambda p: p[0])
    else:
        for i in range(n):
            tt = t0 + (t1 - t0) * (i / (n - 1))
            pts.append((tt, raw(tt)))
    return pts


def gen(repo, accent, created, stars, releases, assets, snapshots, now, bg_path=None, charlabel="", gold=GOLD):
    t = totals(assets)
    total_dl = t["total"]
    t0, t1 = created, now
    span = max((t1 - t0).total_seconds(), 1)
    n_star = len(stars)
    star_max = nice_max(n_star)
    dl_max = nice_max(total_dl)

    def X(dt):
        return M_L + (dt - t0).total_seconds() / span * PLOT_W

    def Y1(n):
        return P1_TOP + P1_H - n / star_max * P1_H

    def Y2(n):
        return P2_TOP + P2_H - n / dl_max * P2_H

    # —— star 曲线（高斯平滑 + 单调插值 → 平滑弧线）
    star_pts = [(M_L, P1_TOP + P1_H)]
    for tt, v in smooth_accum(stars, t0, t1):
        star_pts.append((X(tt), Y1(v)))
    star_pts.append((X(t1), Y1(n_star)))
    star_d = smooth_path(star_pts)
    star_area = star_d + " L %.1f,%.1f L %.1f,%.1f Z" % (X(t1), P1_TOP + P1_H, M_L, P1_TOP + P1_H)

    # —— download 曲线（同样平滑）
    dl_pts = [(X(dt), Y2(min(v, dl_max))) for dt, v in build_dl_curve(assets, snapshots, t0, t1, total_dl)]
    if not dl_pts:
        dl_pts = [(M_L, P2_TOP + P2_H), (X(t1), Y2(total_dl))]
    dl_d = smooth_path(dl_pts)
    dl_area = dl_d + " L %.1f,%.1f L %.1f,%.1f Z" % (X(t1), P2_TOP + P2_H, M_L, P2_TOP + P2_H)

    bg = ""
    if bg_path and os.path.exists(bg_path):
        # cover 裁剪：数值算好偏移，不依赖 preserveAspectRatio（Chrome 顶层 SVG 对它不可靠）
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

    def grid_panel(top, h, vmax, yf):
        g, lab = [], []
        for i in range(5):
            v = vmax * i / 4
            y = yf(v)
            g.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#8f86ad" stroke-opacity="0.26" stroke-width="1"/>' % (M_L, y, W - M_R, y))
            if i == 0:
                lab.append('<text x="%.1f" y="%.1f" text-anchor="end" class="ax">%d</text>' % (M_L - 8, y - 6, v))
            elif i == 4:
                lab.append('<text x="%.1f" y="%.1f" text-anchor="end" class="ax">%d</text>' % (M_L - 8, y + 13, v))
            else:
                lab.append('<text x="%.1f" y="%.1f" text-anchor="end" class="ax">%d</text>' % (M_L - 8, y + 4, v))
        return g, lab

    grid1, lab1 = grid_panel(P1_TOP, P1_H, star_max, Y1)
    grid2, lab2 = grid_panel(P2_TOP, P2_H, dl_max, Y2)

    xticks, xlabels = [], []
    days = span / 86400
    fmt = "%m-%d" if days < 400 else "%Y-%m"
    for i in range(5):
        tt = t0 + datetime.timedelta(seconds=span * i / 4)
        x = X(tt)
        xticks.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#8f86ad" stroke-opacity="0.26" stroke-width="1"/>'
                      % (x, P1_TOP, x, P2_TOP + P2_H))
        if i == 0:
            xlabels.append('<text x="%.1f" y="%.1f" text-anchor="start" class="ax">%s</text>' % (M_L, X_LABEL_Y, tt.strftime(fmt)))
        elif i == 4:
            xlabels.append('<text x="%.1f" y="%.1f" text-anchor="end" class="ax">%s</text>' % (W - M_R, X_LABEL_Y, tt.strftime(fmt)))
        else:
            xlabels.append('<text x="%.1f" y="%.1f" text-anchor="middle" class="ax">%s</text>' % (x, X_LABEL_Y, tt.strftime(fmt)))

    # —— release 竖线：贯穿两个面板，标签在顶部
    rel_lines, rel_marks = [], []
    groups = []
    for r in releases:
        if not (t0 <= r["at"] <= t1):
            continue
        x = X(r["at"])
        if groups and x - groups[-1][0] < 30:
            groups[-1][1].append(r["tag"])
        else:
            groups.append([x, [r["tag"]]])
    for i, (x, tags) in enumerate(groups):
        rel_lines.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-opacity="0.55" stroke-width="1.1" stroke-dasharray="4 4"/>'
                         % (x, P1_TOP, x, P2_TOP + P2_H, gold))
        label = " / ".join(tags)
        if len(label) > 14:
            label = label[:13] + "…"
        anchor = "start" if x < W - M_R - 90 else "end"
        lx = max(x + 4, M_L + 56) if anchor == "start" else x - 4
        rel_marks.append('<text x="%.1f" y="%.1f" text-anchor="%s" class="rel">%s</text>'
                         % (lx, P1_TOP - 8 - (i % 2) * 14, anchor, esc(label)))

    sx, sy = X(t1), Y1(n_star)
    dx, dy = X(t1), Y2(min(total_dl, dl_max))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
  <title id="t">{esc(repo)} · star &amp; download history</title>
  <desc id="d">{n_star} stars and {total_dl} release downloads from {t0.date()} to {t1.date()}</desc>
  <defs>
    <linearGradient id="fillStar" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.32"/>
      <stop offset="100%" stop-color="{accent}" stop-opacity="0.02"/>
    </linearGradient>
    <linearGradient id="fillDl" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.28"/>
      <stop offset="100%" stop-color="{accent}" stop-opacity="0.02"/>
    </linearGradient>
    <linearGradient id="veil" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.88"/>
      <stop offset="22%" stop-color="#ffffff" stop-opacity="0.30"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0.26"/>
    </linearGradient>
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
  <text x="{M_L}" y="30" class="ttl">★⬇ {esc(repo)} · Star &amp; Download History</text>
  <text x="{M_L}" y="50" class="sub">{((charlabel + ' · ') if charlabel else '')}{n_star} stars · {total_dl} 次下载（Gerber {t["gerber"]} · 工程 {t["proj"]}{(" · 图 " + str(t["other"])) if t["other"] else ""}） · {t0.date()} → {t1.date()}</text>
  {''.join(rel_marks)}
  {''.join(grid1)}
  {''.join(grid2)}
  {''.join(xticks)}
  <text x="{M_L + 8}" y="{P1_TOP + 16}" class="pt">★ Star History</text>
  <text x="{M_L + 8}" y="{P2_TOP + 16}" class="pt">⬇ Download History</text>
  {''.join(rel_lines)}
  {''.join(lab1)}
  {''.join(lab2)}
  {''.join(xlabels)}
  <path d="{star_area}" fill="url(#fillStar)"/>
  <path d="{dl_area}" fill="url(#fillDl)"/>
  <path d="{star_d}" fill="none" stroke="#ffffff" stroke-opacity="0.72" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/>
  <path d="{star_d}" fill="none" stroke="{accent}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>
  <path d="{dl_d}" fill="none" stroke="#ffffff" stroke-opacity="0.72" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/>
  <path d="{dl_d}" fill="none" stroke="{accent}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>
  <circle cx="{sx:.1f}" cy="{sy:.1f}" r="4.2" fill="{accent}" stroke="#ffffff" stroke-width="2"/>
  <text x="{min(sx - 6, W - M_R - 6):.1f}" y="{sy - 10:.1f}" text-anchor="end" class="val">★ {n_star}</text>
  <circle cx="{dx:.1f}" cy="{dy:.1f}" r="4.2" fill="{accent}" stroke="#ffffff" stroke-width="2"/>
  <text x="{min(dx - 6, W - M_R - 6):.1f}" y="{dy - 10:.1f}" text-anchor="end" class="val">⬇ {total_dl}</text>
  <text x="{M_L}" y="{H - 14}" class="ax">Source: GitHub stargazers &amp; releases API · 每日自动快照 · {len(snapshots)} 个下载快照</text>
</svg>
'''


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_snap = "--snapshot" in sys.argv
    repo, accent, out = args[0], args[1], args[2]
    bgp = args[3] if len(args) > 3 and args[3] else DEFAULT_BG
    charlabel = args[4] if len(args) > 4 else ""
    gold = args[5] if len(args) > 5 and args[5] else GOLD

    created, stars, releases, assets = fetch(repo)
    t = totals(assets)
    now = datetime.datetime.now(datetime.timezone.utc)
    hist = save_snapshot(repo, assets, now) if do_snap else load_hist()
    snapshots = hist.get("snapshots", [])

    svg = gen(repo, accent, created, stars, releases, assets, snapshots, now,
              bgp if os.path.exists(bgp) else None, charlabel, gold)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    open(out, "w", encoding="utf-8").write(svg)
    print("%s -> %d stars, %d downloads (%d assets), %d snapshots, svg %d bytes"
          % (repo, len(stars), t["total"], len(assets), len(snapshots), len(svg.encode())))
