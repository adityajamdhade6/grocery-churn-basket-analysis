"""Builds dashboard/dashboard.html (self-contained, no external libraries) and copies the Power BI / Tableau-ready extracts."""
from pathlib import Path
import shutil, html, pandas as pd

root = Path(__file__).resolve().parent.parent
R = lambda n: pd.read_csv(root / "results" / f"{n}.csv")
summary, dept, vol, prod, back = R("risk_summary").set_index("risk_tier"), R("dept_repeat"), R("volume_by_week_since_first_order"), R("top_repeat_products"), R("risk_backtest")
(root / "dashboard" / "data").mkdir(parents=True, exist_ok=True)
# ---- tidy extracts for one-click import into Power BI / Tableau (derived from results/*.csv only)
D = root / "dashboard" / "data"
for f in D.glob("*.csv"): f.unlink()
shutil.copy(root / "results" / "customer_risk.csv", D / "customer_risk.csv")
shutil.copy(root / "results" / "volume_by_week_since_first_order.csv", D / "volume_by_week_since_first_order.csv")
dept.sort_values("reorder_rate_pct", ascending=False).to_csv(D / "dept_repeat.csv", index=False)
rs = R("risk_summary"); rs["tier_sort"] = rs.risk_tier.map({"High risk": 1, "Watch": 2, "Healthy": 3}); rs.sort_values("tier_sort").to_csv(D / "risk_summary.csv", index=False)
prod.sort_values("times_reordered", ascending=False).head(10).astype({"times_reordered": int})[["product_name", "department", "times_bought", "times_reordered", "reorder_rate_pct"]].to_csv(D / "top10_products.csv", index=False)
_total = int(rs.customers.sum()); _hi = int(rs[rs.risk_tier == "High risk"].customers.iloc[0]); _wa = int(rs[rs.risk_tier == "Watch"].customers.iloc[0])
_reg = back[back.cadence.str.startswith("Regular")].set_index("tier_at_order_6").pct_who_faded
_rr = dept.items_reordered.sum() / dept.items_ordered.sum() * 100
pd.DataFrame({"kpi_order": [1, 2, 3, 4],
    "kpi_label": ["Customers who just went 30+ days between orders", "Regular shoppers who faded: after a 30+ day gap vs kept rhythm", "Regular shoppers running 1.5x+ later than their own normal", "Share of all items bought that are repeats"],
    "kpi_display": [f"{_hi:,} ({_hi/_total:.0%})", f"{_reg['High risk']:.0f}% vs {_reg['Healthy']:.0f}%", f"{_wa:,}", f"{_rr:.0f}%"]}).to_csv(D / "kpis.csv", index=False)

total = int(summary.customers.sum()); hi, wa = int(summary.loc["High risk", "customers"]), int(summary.loc["Watch", "customers"])
overall_rr = dept.items_reordered.sum() / dept.items_ordered.sum() * 100
reg = back[back.cadence.str.startswith("Regular")].set_index("tier_at_order_6").pct_who_faded
TEAL, ORANGE, AMBER, MID = "var(--teal)", "var(--orange)", "var(--amber)", "var(--mid)"
esc = html.escape

def hbar(rows, w=520, row_h=26, label_w=130, vmax=None, fmt="{:.0f}%", sub=None):
    vmax = vmax or max(v for _, v, _ in rows); h = row_h * len(rows) + 6; bw = w - label_w - (150 if sub else 60); out = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    for i, (lab, v, col) in enumerate(rows):
        y = i * row_h + 3; L = max(2, bw * v / vmax)
        out.append(f'<text x="{label_w-8}" y="{y+row_h/2+4}" text-anchor="end" class="lab">{esc(lab)}</text>'
                   f'<rect x="{label_w}" y="{y+3}" width="{L:.1f}" height="{row_h-8}" rx="3" fill="{col}"><title>{esc(lab)}: {fmt.format(v)}</title></rect>'
                   f'<text x="{label_w+L+6}" y="{y+row_h/2+4}" class="val">{fmt.format(v)}{(" · " + sub[i]) if sub else ""}</text>')
    return "".join(out) + "</svg>"

def line(xs, ys, w=520, h=230):
    pl, pr, pt, pb = 46, 12, 10, 28; ymax = max(ys) * 1.05
    X = lambda x: pl + (w - pl - pr) * (x - xs[0]) / (xs[-1] - xs[0]); Y = lambda y: pt + (h - pt - pb) * (1 - y / ymax)
    pts = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in zip(xs, ys))
    o = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    for t in range(0, int(ymax), 50000 if ymax > 100000 else 20000):
        o.append(f'<line x1="{pl}" x2="{w-pr}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" class="gl"/><text x="{pl-6}" y="{Y(t)+4:.1f}" text-anchor="end" class="axis">{t//1000}k</text>')
    for x in range(0, xs[-1] + 1, 13):
        o.append(f'<text x="{X(x):.1f}" y="{h-8}" text-anchor="middle" class="axis">wk {x}</text>')
    o.append(f'<polygon points="{X(xs[0]):.1f},{Y(0):.1f} {pts} {X(xs[-1]):.1f},{Y(0):.1f}" fill="{TEAL}" opacity=".15"/>'
             f'<polyline points="{pts}" fill="none" stroke="{TEAL}" stroke-width="2.5" stroke-linejoin="round"/>')
    return "".join(o) + "</svg>"

v = vol[vol.week_since_first_order < 52]
volume_svg = line(list(v.week_since_first_order), list(v.orders))
risk_svg = hbar([("High risk", hi, ORANGE), ("Watch", wa, AMBER), ("Healthy", total - hi - wa, TEAL)], fmt="{:,.0f}", label_w=90,
                sub=[f"{hi/total:.0%}", f"{wa/total:.0%}", f"{(total-hi-wa)/total:.0%}"], row_h=44)
d = dept.sort_values("reorder_rate_pct", ascending=False)
proof_svg = hbar([("30+ day gap", reg["High risk"], ORANGE), ("1.5x+ later", reg["Watch"], AMBER), ("Kept rhythm", reg["Healthy"], TEAL)], fmt="{:.0f}%", label_w=90, row_h=34, vmax=40)
dept_svg = hbar([(r.department.title(), r.reorder_rate_pct, TEAL if r.reorder_rate_pct >= 60 else MID if r.reorder_rate_pct >= 45 else ORANGE) for r in d.itertuples()],
                row_h=19, vmax=100, label_w=118)
p = prod.sort_values("times_reordered", ascending=False).head(10)
prod_svg = hbar([(r.product_name[:26], r.times_reordered / 1000, TEAL) for r in p.itertuples()], row_h=26, label_w=190,
                fmt="{:,.0f}k", sub=[f"{r.reorder_rate_pct:.0f}% repeat" for r in p.itertuples()])

page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Retention Dashboard</title><style>
:root{{--bg:#F6F8F8;--card:#fff;--ink:#1F2A37;--muted:#5B6573;--line:#E3E8EB;--teal:#1B7F79;--orange:#E07B39;--amber:#E8B84A;--mid:#9CB9B6}}
@media(prefers-color-scheme:dark){{:root{{--bg:#12171C;--card:#1B222A;--ink:#E8ECEF;--muted:#9AA5B1;--line:#2B343D;--teal:#3FB3AA;--orange:#F0904F;--amber:#EBC15F;--mid:#5E8480}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:24px 16px 32px}}
h1{{font-size:24px;margin:0 0 4px}}.sub{{color:var(--muted);margin:0 0 18px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
.kpi b{{display:block;font-size:30px;line-height:1.1}}.kpi span{{color:var(--muted);font-size:13px}}
.warn b{{color:var(--orange)}}.good b{{color:var(--teal)}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
h2{{font-size:15px;margin:0 0 2px}}.card p{{margin:0 0 8px;color:var(--muted);font-size:13px}}
svg{{width:100%;height:auto;display:block}}.lab{{font-size:12px;fill:var(--ink)}}.val{{font-size:12px;fill:var(--muted)}}.axis{{font-size:11px;fill:var(--muted)}}.gl{{stroke:var(--line)}}
footer{{color:var(--muted);font-size:12px;margin-top:14px}}
@media(max-width:820px){{.kpis{{grid-template-columns:1fr 1fr}}.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>Who is about to stop ordering, and what brings people back?</h1>
<p class="sub">{total:,} customers · 3.4M orders · Instacart grocery data used as a quick-commerce proxy</p>
<div class="kpis">
<div class="card kpi warn"><b>{hi:,}</b><span>customers just went 30+ days between orders ({hi/total:.0%})</span></div>
<div class="card kpi warn"><b>{reg["High risk"]:.0f}% vs {reg["Healthy"]:.0f}%</b><span>regular shoppers who faded after a 30+ day gap vs. those who kept rhythm</span></div>
<div class="card kpi"><b>{wa:,}</b><span>regular shoppers running 1.5x+ later than their own normal</span></div>
<div class="card kpi good"><b>{overall_rr:.0f}%</b><span>of all items bought are repeats</span></div></div>
<div class="grid">
<div class="card"><h2>Churn risk: 3 in 10 customers have just had a month-long gap</h2><p>Customers by risk tier at their latest order</p>{risk_svg}<h2 style="margin-top:16px">And it works: share who faded afterwards</h2><p>Back-test on regular shoppers at their 6th order (faded = 2 or fewer further orders)</p>{proof_svg}</div>
<div class="card"><h2>Fresh staples are the habit: dairy and produce are re-bought ~2 of 3 times</h2><p>Repeat rate by department (teal ≥ 60%, orange &lt; 45%)</p>{dept_svg}</div>
<div class="card"><h2>Orders taper steadily after a customer's first weeks</h2><p>Orders per week since each customer's first order. The taper mixes real drop-off with shorter data history for later weeks</p>{volume_svg}</div>
<div class="card"><h2>Bananas, strawberries, avocados and spinach drive repeat orders</h2><p>Top 10 products by number of repeat purchases (thousands)</p>{prod_svg}</div>
</div>
<footer>Risk tiers: High = latest gap 30+ days. Watch = usual gap under 12 days and now 1.5x+ longer. Back-test on 6th order. See README for method and limits. US weekly-grocery data, so quick-commerce thresholds need re-tuning.</footer>
</main></body></html>'''
(root / "dashboard" / "dashboard.html").write_text(page)
print("wrote dashboard.html", len(page))
