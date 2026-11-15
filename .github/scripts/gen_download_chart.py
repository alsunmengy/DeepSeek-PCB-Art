#!/usr/bin/env python3
"""自绘 GitHub release 下载历史 SVG（download history），风格与 star-history 一致。

用法:
  # 只画图（不写历史）
  python3 gen_download_chart.py <owner/repo> <accent> <out.svg> [bg.jpg] [charlabel]
  # 采集一个快照进历史文件，再画图（GitHub Action 每天跑这个）
  python3 gen_download_chart.py <owner/repo> <accent> <out.svg> [bg.jpg] [charlabel] --snapshot

数据来源:
  * releases / assets 的 download_count + created_at（累计值，GitHub 无历史时间序列）
  * .github/download-history/history.json：每天采集的累计快照，真实曲线由此长出
  * 快照之前的区间按 asset 创建时间做"均匀线性回推"，图上用虚线标注为估算
"""
import base64
import datetime
import json
import math
import os
import subprocess
import sys

W, H = 800, 460
M_L, M_R, M_T, M_B = 60, 30, 112, 46
PLOT_W, PLOT_H = W - M_L - M_R, H - M_T - M_B
DEFAULT_BG = ".github/star-history/bg.jpg"
HIST = ".github/download-history/history.json"

C_MAIN = None      # accent
C_PROJ = "#5A3FA8"
C_GERB = "#B07E1E"


def gh(args):
    out = subprocess.run(["gh", "api"] + args, capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def parse_t(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def kind_of(name):
    low = name.lower()
    if low.endswith(".epro2") or low.endswith(".zip") and "gerber" not in low:
        return "proj"
    if "gerber" in low or low.endswith(".zip"):
        return "gerber"
    return "other"


def fetch(repo):
    meta = gh(["repos/" + repo])
    rel, page = [], 1
    while True:
        batch = gh(["repos/%s/releases?per_page=100&page=%d" % (repo, page)])
        if not batch:
            break
        rel += batch
        if len(batch) < 100:
            break
        page += 1
    assets = []
    for r in rel:
        for a in r.get("assets", []):
            assets.append({
                "rel": r.get("tag_name") or str(r.get("id")),
                "name": a["name"],
                "dl": a.get("download_count") or 0,
                "at": parse_t(a.get("created_at") or r.get("published_at")),
                "kind": kind_of(a["name"]),
            })
    asked = [({"tag": r["tag_name"], "at": parse_t(r["published_at"])} if r.get("published_at") else None) for r in rel]
    releases = sorted([x for x in asked if x], key=lambda x: x["at"])
    return meta, assets, releases


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


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def nice_max(v):
    """给纵轴取好看的 4 等分步长（1/1.25/1.5/2/2.5/3/4/5/6/8 × 10^k）。"""
    if v <= 0:
        return 4
    need = math.ceil(v / 4)
    k = 10 ** max(0, len(str(need)) - 1)
    for m in (1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if m * k >= need:
            return int(round(m * k)) * 4
    return need * 4


def gen(repo, accent, gold, assets, releases, snapshots, t_start, now, bg_path=None, charlabel=""):
    t = totals(assets)
    t0, t1 = t_start, now
    span = max((t1 - t0).total_seconds(), 1)
    ymax = nice_max(t["total"])

    def X(dt):
        return M_L + (dt - t0).total_seconds() / span * PLOT_W

    def Y(n):
        return M_T + PLOT_H - n / ymax * PLOT_H

    def growth(a, tt):
        """单个 asset 的估算累计：发布后先陡升再放缓（时间常数 ~6 天），到 now 正好落到当前值。"""
        if tt <= a["at"]:
            return 0.0
        tau = 6 * 86400.0
        dt = (tt - a["at"]).total_seconds()
        life = max((t1 - a["at"]).total_seconds(), 1)
        f = (1 - math.exp(-dt / tau)) / (1 - math.exp(-life / tau))
        return a["dl"] * min(1.0, f)

    def line_for(key):
        pts = []
        for i in range(73):
            tt = t0 + datetime.timedelta(seconds=span * i / 72)
            v = 0.0
            for a in assets:
                if key == "total":
                    v += growth(a, tt)
                elif a["kind"] == key:
                    v += growth(a, tt)
            pts.append((X(tt), Y(min(v, ymax))))
        return pts

    def ss(pts):
        return " ".join("%.1f,%.1f" % p for p in pts)

    est_total = line_for("total")
    est_proj = line_for("proj")
    est_gerb = line_for("gerber")

    # 真实快照段
    snaps = [s for s in snapshots if s.get("t")]
    real_pts = []
    for s in snaps:
        st = parse_t(s["t"])
        if st < t0:
            st = t0
        real_pts.append((X(min(st, t1)), Y(min(s["total"], ymax))))

    bg = ""
    if bg_path and os.path.exists(bg_path):
        b64 = base64.b64encode(open(bg_path, "rb").read()).decode()
        bg = '<image x="0" y="0" width="%d" height="%d" href="data:image/jpeg;base64,%s"/>' % (W, H, b64)

    grid, ylabels = [], []
    for i in range(5):
        v = ymax * i / 4
        y = Y(v)
        grid.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#8f86ad" stroke-opacity="0.28" stroke-width="1"/>' % (M_L, y, W - M_R, y))
        if i == 0:
            ylabels.append('<text x="%.1f" y="%.1f" text-anchor="end" class="ax">%d</text>' % (M_L - 8, y - 6, v))
        elif i == 4:
            ylabels.append('<text x="%.1f" y="%.1f" text-anchor="end" class="ax">%d</text>' % (M_L - 8, y + 13, v))
        else:
            ylabels.append('<text x="%.1f" y="%.1f" text-anchor="end" class="ax">%d</text>' % (M_L - 8, y + 4, v))

    xticks, xlabels = [], []
    days = span / 86400
    fmt = "%m-%d" if days < 400 else "%Y-%m"
    for i in range(5):
        tt = t0 + datetime.timedelta(seconds=span * i / 4)
        x = X(tt)
        xticks.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#8f86ad" stroke-opacity="0.28" stroke-width="1"/>' % (x, M_T, x, M_T + PLOT_H))
        if i == 0:
            xlabels.append('<text x="%.1f" y="%.1f" text-anchor="start" class="ax">%s</text>' % (M_L, M_T + PLOT_H + 20, tt.strftime(fmt)))
        elif i == 4:
            xlabels.append('<text x="%.1f" y="%.1f" text-anchor="end" class="ax">%s</text>' % (W - M_R, M_T + PLOT_H + 20, tt.strftime(fmt)))
        else:
            xlabels.append('<text x="%.1f" y="%.1f" text-anchor="middle" class="ax">%s</text>' % (x, M_T + PLOT_H + 20, tt.strftime(fmt)))

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
        rel_lines.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-opacity="0.7" stroke-width="1.2" stroke-dasharray="4 4"/>' % (x, M_T, x, M_T + PLOT_H, gold))
        label = " / ".join(tags)
        if len(label) > 14:
            label = label[:13] + "…"
        lx = min(max(x + 4, M_L + 4), W - M_R - 8)
        ly = M_T - 8 - (i % 2) * 15
        anchor = "start" if lx < W - M_R - 90 else "end"
        rel_marks.append('<text x="%.1f" y="%.1f" text-anchor="%s" class="rel">%s</text>' % (lx if anchor == "start" else lx + 6, ly, anchor, esc(label)))

    end_x, end_y = X(t1), Y(min(t["total"], ymax))
    area = ss(est_total) + " %.1f,%.1f %.1f,%.1f" % (end_x, M_T + PLOT_H, M_L, M_T + PLOT_H)
    real_line = ss(real_pts) if len(real_pts) > 1 else ""

    first_snap_day = parse_t(snaps[0]["t"]).date().isoformat() if snaps else None
    est_note = ("实线 = 真实快照（自 %s 起每日采集）· 虚线 = 发布锚点均匀回推的估算" % first_snap_day) if snaps \
        else "尚无快照数据 · 曲线为按 release 发布时间的均匀回推估算"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
  <title id="t">{esc(repo)} download history</title>
  <desc id="d">{t["total"]} total release downloads, {t["gerber"]} Gerber, {t["proj"]} project files</desc>
  <defs>
    <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.34"/>
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
    .ax{{font:400 11.5px -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;fill:#4f4864;stroke:#ffffff;stroke-opacity:0.85;stroke-width:2.6;paint-order:stroke fill}}
    .val{{font:700 13px -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;fill="{accent}";stroke:#ffffff;stroke-opacity:0.9;stroke-width:2.8;paint-order:stroke fill}}
    .rel{{font:400 10.5px ui-monospace,SFMono-Regular,Menlo,monospace;fill:{gold}}}
    .lg{{font:400 11px -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;fill:#4f4864;stroke:#ffffff;stroke-opacity:0.85;stroke-width:2.6;paint-order:stroke fill}}
  </style>
  <text x="{M_L}" y="30" class="ttl">⬇ {esc(repo)} · Download History</text>
  <text x="{M_L}" y="50" class="sub">{((charlabel + ' · ') if charlabel else '')}{t["total"]} 次下载 · Gerber {t["gerber"]} · 工程文件 {t["proj"]}{("  ·  图片 " + str(t["other"])) if t["other"] else ""} · {t0.date()} → {t1.date()}</text>
  <g transform="translate({M_L + 12},{M_T + 18})">
    <rect x="0" y="-7" width="14" height="3" fill="{accent}"/><text x="19" y="0" class="lg">总下载</text>
    <rect x="70" y="-7" width="14" height="3" fill="{gold}"/><text x="89" y="0" class="lg">Gerber</text>
    <rect x="140" y="-7" width="14" height="3" fill="{C_PROJ}"/><text x="159" y="0" class="lg">工程</text>
  </g>
  {''.join(grid)}
  {''.join(xticks)}
  {''.join(rel_lines)}
  {''.join(rel_marks)}
  {''.join(ylabels)}
  {''.join(xlabels)}
  <polygon points="{area}" fill="url(#fill)"/>
  <polyline points="{ss(est_total)}" fill="none" stroke="{accent}" stroke-opacity="0.55" stroke-width="1.8" stroke-dasharray="5 5" stroke-linejoin="round"/>
  <polyline points="{ss(est_gerb)}" fill="none" stroke="{gold}" stroke-opacity="0.75" stroke-width="1.4" stroke-dasharray="4 4" stroke-linejoin="round"/>
  <polyline points="{ss(est_proj)}" fill="none" stroke="{C_PROJ}" stroke-opacity="0.75" stroke-width="1.4" stroke-dasharray="4 4" stroke-linejoin="round"/>
  {('<polyline points="%s" fill="none" stroke="#ffffff" stroke-opacity="0.75" stroke-width="6" stroke-linejoin="round" stroke-linecap="round"/>' % real_line) if real_line else ''}
  {('<polyline points="%s" fill="none" stroke="%s" stroke-width="2.8" stroke-linejoin="round" stroke-linecap="round"/>' % (real_line, accent)) if real_line else ''}
  <circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="4.5" fill="{accent}" stroke="#ffffff" stroke-width="2"/>
  <text x="{min(end_x - 6, W - M_R - 6):.1f}" y="{end_y - 12:.1f}" text-anchor="end" class="val">⬇ {t["total"]}</text>
  <text x="{M_L}" y="{H - 12}" class="ax">{esc(est_note)}</text>
</svg>
'''


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_snap = "--snapshot" in sys.argv
    repo, accent, out = args[0], args[1], args[2]
    bgp = args[3] if len(args) > 3 else DEFAULT_BG
    charlabel = args[4] if len(args) > 4 else ""
    gold = "#B07E1E"

    meta, assets, releases = fetch(repo)
    t = totals(assets)
    now = datetime.datetime.now(datetime.timezone.utc)
    hist = save_snapshot(repo, assets, now) if do_snap else load_hist()
    snapshots = hist.get("snapshots", [])

    starts = [a["at"] for a in assets] or [parse_t(meta["created_at"])]
    t_start = min(starts + [parse_t(meta["created_at"])])
    if t_start >= now:
        t_start = now - datetime.timedelta(days=1)

    svg = gen(repo, accent, gold, assets, releases, snapshots, t_start, now,
              bgp if os.path.exists(bgp) else None, charlabel)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    open(out, "w", encoding="utf-8").write(svg)
    print("%s -> total %d (gerber %d, proj %d, other %d), %d assets, %d snapshots, svg %d bytes"
          % (repo, t["total"], t["gerber"], t["proj"], t["other"], len(assets), len(snapshots), len(svg.encode())))
