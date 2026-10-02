#!/usr/bin/env python3
"""自绘 GitHub star history SVG：从仓库创建日到今天，主题色可配，release 垂直线标注。
用法: python3 gen_chart.py <owner/repo> <color> <out.svg>
数据来源: gh api（stargazers 带 starred_at + releases）
"""
import json, subprocess, sys, datetime, math, os

W, H = 800, 460
M_L, M_R, M_T, M_B = 60, 30, 112, 46
PLOT_W, PLOT_H = W - M_L - M_R, H - M_T - M_B


def gh(args):
    out = subprocess.run(["gh", "api"] + args, capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def fetch(repo):
    meta = gh(["repos/" + repo])
    created = datetime.datetime.fromisoformat(meta["created_at"].replace("Z", "+00:00"))
    stars, page = [], 1
    while True:
        batch = gh(["repos/%s/stargazers?per_page=100&page=%d" % (repo, page),
                    "-H", "Accept: application/vnd.github.star+json"])
        if not batch:
            break
        stars += [datetime.datetime.fromisoformat(s["starred_at"].replace("Z", "+00:00")) for s in batch]
        if len(batch) < 100:
            break
        page += 1
    stars.sort()
    # releases（用于垂直线标注）；没有 release 的 tag 不画
    rel, page = [], 1
    while True:
        batch = gh(["repos/%s/releases?per_page=100&page=%d" % (repo, page)])
        if not batch:
            break
        for x in batch:
            if x.get("published_at"):
                rel.append((x["tag_name"], datetime.datetime.fromisoformat(x["published_at"].replace("Z", "+00:00"))))
        if len(batch) < 100:
            break
        page += 1
    rel.sort(key=lambda p: p[1])
    return meta, created, stars, rel


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def gen(repo, color, stars, created, releases):
    now = datetime.datetime.now(datetime.timezone.utc)
    total = len(stars)
    t0, t1 = created, now
    span = max((t1 - t0).total_seconds(), 1)

    def X(t):
        return M_L + (t - t0).total_seconds() / span * PLOT_W

    def Y(n):
        step = max(1, math.ceil(max(total, 1) / 4))
        nice = step * 4
        return M_T + PLOT_H - n / nice * PLOT_H, nice

    _, ytop_nice = Y(total)

    pts = [(M_L, M_T + PLOT_H)]
    n = 0
    for t in stars:
        n += 1
        pts.append((X(t), Y(n)[0]))
    pts.append((X(t1), Y(total)[0]))
    line = " ".join("%.1f,%.1f" % p for p in pts)
    area = line + " %.1f,%.1f %.1f,%.1f" % (X(t1), M_T + PLOT_H, M_L, M_T + PLOT_H)

    grid, ylabels = [], []
    for i in range(5):
        v = ytop_nice * i / 4
        y = M_T + PLOT_H - (v / ytop_nice) * PLOT_H
        grid.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#eaeaea" stroke-width="1"/>' % (M_L, y, W - M_R, y))
        ylabels.append('<text x="%.1f" y="%.1f" text-anchor="end" class="ax">%d</text>' % (M_L - 8, y + 4, v))

    xticks, xlabels = [], []
    days = span / 86400
    for i in range(5):
        t = t0 + datetime.timedelta(seconds=span * i / 4)
        x = X(t)
        xticks.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#eaeaea" stroke-width="1"/>' % (x, M_T, x, M_T + PLOT_H))
        xlabels.append('<text x="%.1f" y="%.1f" text-anchor="middle" class="ax">%s</text>' % (x, M_T + PLOT_H + 20, t.strftime("%m-%d") if days < 400 else t.strftime("%Y-%m")))

    # release 垂直线 + 竖排 tag 标签（三层错开防重叠）
    rel_lines, rel_marks = [], []
    lvl = 0
    for tag, t in releases:
        if not (t0 <= t <= t1):
            continue
        x = X(t)
        rel_lines.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#b9b9b9" stroke-width="1" stroke-dasharray="4 4"/>'
                         % (x, M_T, x, M_T + PLOT_H))
        ty = M_T - 8 - (lvl % 3) * 17
        label = tag if len(tag) <= 16 else tag[:15] + "…"
        rel_marks.append('<text transform="translate(%.1f,%.1f) rotate(-90)" class="rel">%s</text>'
                         % (x + 4, ty, esc(label)))
        lvl += 1

    end_x, end_y = X(t1), Y(total)[0]
    label_x = min(end_x - 6, W - M_R - 6)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
  <title id="t">{esc(repo)} star history</title>
  <desc id="d">{total} GitHub stars from {t0.date()} to {t1.date()}, {len(rel_lines)} releases marked</desc>
  <defs>
    <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{color}" stop-opacity="0.30"/>
      <stop offset="100%" stop-color="{color}" stop-opacity="0.02"/>
    </linearGradient>
  </defs>
  <rect width="{W}" height="{H}" fill="#ffffff"/>
  <style>
    .ttl{{font:700 17px -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;fill:#1f2328}}
    .sub{{font:400 12.5px -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;fill:#656d76}}
    .ax{{font:400 11.5px -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;fill:#656d76}}
    .val{{font:700 13px -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;fill="{color}"}}
    .rel{{font:400 10.5px ui-monospace,SFMono-Regular,Menlo,monospace;fill:#6b7280}}
  </style>
  <text x="{M_L}" y="30" class="ttl">★ {esc(repo)} · Star History</text>
  <text x="{M_L}" y="50" class="sub">{total} stars · {t0.date()} → {t1.date()}（创建至今）{("  ·  " + str(len(rel_lines)) + " 个 release") if rel_lines else ""}</text>
  {''.join(grid)}
  {''.join(xticks)}
  {''.join(rel_lines)}
  {''.join(rel_marks)}
  {''.join(ylabels)}
  {''.join(xlabels)}
  <polygon points="{area}" fill="url(#fill)"/>
  <polyline points="{line}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
  <circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="4.5" fill="{color}" stroke="#ffffff" stroke-width="2"/>
  <text x="{label_x:.1f}" y="{end_y - 12:.1f}" text-anchor="end" class="val">★ {total}</text>
  <text x="{M_L}" y="{H - 12}" class="ax">Source: GitHub stargazers &amp; releases API · auto-updated</text>
</svg>
'''


if __name__ == "__main__":
    repo, color, out = sys.argv[1], sys.argv[2], sys.argv[3]
    meta, created, stars, releases = fetch(repo)
    svg = gen(repo, color, stars, created, releases)
    open(out, "w", encoding="utf-8").write(svg)
    print("%s -> %d stars, created %s, %d releases, svg %d bytes"
          % (repo, len(stars), created.date(), len(releases), len(svg.encode())))
