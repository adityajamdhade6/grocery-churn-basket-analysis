"""Builds excel/Instacart_Basket_Analysis.xlsx from the DuckDB database and results/*.csv.
Pivot-style tables are live formulas (AVERAGEIFS / SUMIFS / COUNTIFS) over the Orders_Data tab, so they recalculate in Excel
and Google Sheets. Every formula also carries its computed value so the file reads correctly in viewers that do not recalculate."""
from pathlib import Path
import duckdb, pandas as pd, xlsxwriter

root = Path(__file__).resolve().parent.parent
R = lambda n: pd.read_csv(root / "results" / f"{n}.csv")
con = duckdb.connect(str(root / "data" / "instacart.duckdb"), read_only=True)

orders = con.execute("""
    SELECT order_id, user_id, order_number, CAST(order_hour_of_day AS INT) AS hour_of_day, basket_size, reordered_items
    FROM order_facts USING SAMPLE reservoir(50000 ROWS) REPEATABLE (42) ORDER BY order_id""").df()
band = lambda n: "1st order" if n == 1 else "2nd-4th" if n <= 4 else "5th-9th" if n <= 9 else "10th-19th" if n <= 19 else "20th+"
tod = lambda h: "Night (0-5h)" if h < 6 else "Morning (6-11h)" if h < 12 else "Afternoon (12-17h)" if h < 18 else "Evening (18-23h)"
orders["order_stage"] = orders.order_number.map(band)
orders["time_of_day"] = orders.hour_of_day.map(tod)
N = len(orders)

dept, pairs, bk = R("dept_repeat"), R("product_pairs"), R("basket_by_order_number")
summary, back, lift = R("risk_summary"), R("risk_backtest"), R("first_basket_lift")

wb = xlsxwriter.Workbook(root / "excel" / "Instacart_Basket_Analysis.xlsx")
INK, TEAL, MID, ORANGE, PALE = "#000000", "#1F4E79", "#1F4E79", "#1F4E79", "#F2F2F2"   # one dark blue for charts, black text
F = lambda **k: wb.add_format({"font_name": "Calibri", "font_size": 11, "font_color": INK, "valign": "vcenter", **k})
title, sub = F(bold=True, font_size=16), F(font_size=11, font_color="#595959", text_wrap=True, valign="top")
hdr = F(bold=True, bg_color="#D9D9D9", border=1, text_wrap=True, align="center")
hdr_l = F(bold=True, bg_color="#D9D9D9", border=1, text_wrap=True)
txt, num, dec1, dec2, pct1 = F(), F(num_format="#,##0"), F(num_format="0.0"), F(num_format="0.00"), F(num_format='0.0"%"')
note = F(italic=True, font_color="#595959", text_wrap=True, valign="top")
h2 = F(bold=True, font_size=12)
big = F(bold=True, font_size=24, align="center", border=1, num_format='0"%"')
big_o = big
cap = F(font_size=10, font_color="#595959", align="center", text_wrap=True, valign="top")
tag = F(bold=True, font_size=12, bottom=1, align="left")
body = F(font_size=11, text_wrap=True, valign="top")

# ------------------------------------------------------------------ sheets (Summary first)
S = wb.add_worksheet("Summary"); PB = wb.add_worksheet("Pivot_Basket"); PD = wb.add_worksheet("Pivot_Dept_Repeat")
PP = wb.add_worksheet("Pivot_Pairs"); PC = wb.add_worksheet("Churn_Risk"); PK = wb.add_worksheet("Pivot_Check"); OD = wb.add_worksheet("Orders_Data")
for w in (S, PB, PD, PP, PC, PK, OD): w.hide_gridlines(2)

# ------------------------------------------------------------------ Orders_Data
OD.write_row(0, 0, ["order_id", "user_id", "order_number", "hour_of_day", "basket_size", "reordered_items", "order_stage", "time_of_day"], hdr)
for i, r in enumerate(orders.itertuples(index=False), start=1):
    OD.write_row(i, 0, list(r))
OD.freeze_panes(1, 0); OD.set_column("A:F", 14); OD.set_column("G:H", 20)
OD.autofilter(0, 0, N, 7)
rng = lambda col: f"Orders_Data!${col}$2:${col}${N+1}"

# ------------------------------------------------------------------ Pivot_Basket
PB.set_column("A:A", 24); PB.set_column("B:E", 16); PB.set_column("G:J", 16)
PB.write("A1", "Basket composition: how big is a basket, and how much of it is repeat?", title)
PB.merge_range("A2:E2", f"The two tables below are native PivotTables built on the Orders_Data tab ({N:,} randomly sampled orders). Right-click > Refresh to recalculate. Tab Pivot_Check re-computes them with formulas as a cross-check.", note)
PB.set_row(1, 32)

def pivot(top, label, key_col, keys, values):
    PK.write(top, 0, label, hdr_l); PK.write_row(top, 1, ["Orders", "Avg basket size (items)", "Repeat items as % of basket"], hdr)
    PK.set_row(top, 32)
    for j, k in enumerate(keys, start=1):
        r = top + j; sub_df = values[values[key_col] == k]
        PK.write(r, 0, k, txt)
        PK.write_formula(r, 1, f'=COUNTIFS({rng(KC[key_col])},A{r+1})', num, len(sub_df))
        PK.write_formula(r, 2, f'=AVERAGEIFS({rng("E")},{rng(KC[key_col])},A{r+1})', dec1, sub_df.basket_size.mean())
        PK.write_formula(r, 3, f'=SUMIFS({rng("F")},{rng(KC[key_col])},A{r+1})/SUMIFS({rng("E")},{rng(KC[key_col])},A{r+1})',
                         F(num_format="0.0%"), sub_df.reordered_items.sum() / sub_df.basket_size.sum())
    r = top + len(keys) + 1
    PK.write(r, 0, "All orders", F(bold=True, top=1))
    PK.write_formula(r, 1, f"=COUNTA({rng('A')})", F(bold=True, top=1, num_format="#,##0"), N)
    PK.write_formula(r, 2, f"=AVERAGE({rng('E')})", F(bold=True, top=1, num_format="0.0"), values.basket_size.mean())
    PK.write_formula(r, 3, f"=SUM({rng('F')})/SUM({rng('E')})", F(bold=True, top=1, num_format="0.0%"), values.reordered_items.sum() / values.basket_size.sum())
KC = {"order_stage": "G", "time_of_day": "H"}
STAGES = ["1st order", "2nd-4th", "5th-9th", "10th-19th", "20th+"]
TIMES = ["Morning (6-11h)", "Afternoon (12-17h)", "Evening (18-23h)", "Night (0-5h)"]
pivot(3, "Customer stage (order number)", "order_stage", STAGES, orders)
pivot(12, "Time of day", "time_of_day", TIMES, orders)
PB.merge_range("A21:D23", "Read it: basket size barely moves with customer stage (~10 items), but the repeat share climbs steadily. A customer's basket does not get bigger, it gets more routine.", body)

# ---- native PivotTable placeholders: rendered values are written here, scripts/add_pivots.py attaches the real PivotTable objects
PIV = {}
def render_pivot(top, key_col, keys):
    PB.write_row(top, 0, ["Row Labels", "Orders", "Avg basket size", "Repeat share of basket"], hdr)
    for j, k in enumerate(keys, start=1):
        d_ = orders[orders[key_col] == k]
        PB.write(top + j, 0, k, txt); PB.write(top + j, 1, len(d_), num)
        PB.write(top + j, 2, d_.basket_size.mean(), dec2); PB.write(top + j, 3, d_.reordered_items.sum() / d_.basket_size.sum(), F(num_format="0.00%"))
    r = top + len(keys) + 1; gb = F(bold=True, top=1)
    PB.write(r, 0, "Grand Total", gb); PB.write(r, 1, len(orders), F(bold=True, top=1, num_format="#,##0"))
    PB.write(r, 2, orders.basket_size.mean(), F(bold=True, top=1, num_format="0.00")); PB.write(r, 3, orders.reordered_items.sum() / orders.basket_size.sum(), F(bold=True, top=1, num_format="0.00%"))
render_pivot(3, "order_stage", STAGES)
render_pivot(12, "time_of_day", TIMES)
# cross-check columns on Pivot_Check: pivot value, then formula minus pivot (should all be 0)
PK.write("A1", "Cross-check: formulas vs. native PivotTables", title)
PK.merge_range("A2:L2", "Columns A-D recompute each PivotTable with SUMIFS/AVERAGEIFS. Columns F-H read the PivotTable cells on Pivot_Basket. Columns J-L subtract them: every difference should be 0 (after a refresh).", note); PK.set_row(1, 32)
PK.write_row(3, 5, ["Pivot: Orders", "Pivot: Avg basket", "Pivot: Repeat share"], hdr); PK.write_row(3, 9, ["Diff: Orders", "Diff: Avg basket", "Diff: Repeat share"], hdr)
PK.set_column("F:L", 16)
KC_ = {3: 'order_stage', 12: 'time_of_day'}
for top, keys in ((3, STAGES), (12, TIMES)):
    for j in range(1, len(keys) + 2):
        r = top + j; x = r + 1
        d_ = orders[orders[KC_[top]] == keys[j - 1]] if j <= len(keys) else orders
        vals = (len(d_), d_.basket_size.mean(), d_.reordered_items.sum() / d_.basket_size.sum())
        for c, (src, fmt) in enumerate((("B", "#,##0"), ("C", "0.00"), ("D", "0.0000"))):
            PK.write_formula(r, 5 + c, f"=Pivot_Basket!{src}{x}", F(num_format=fmt), vals[c])
            PK.write_formula(r, 9 + c, f"=ROUND({src}{x}-{'FGH'[c]}{x},6)", F(num_format="0.000000"), 0)

# chart-2 source (full dataset, orders 1-30)
PB.write("G3", "Full dataset by order number (orders 30+ grouped at 30)", h2)
PB.write_row(3, 6, ["Order number", "Orders", "Avg basket size", "Repeat items % of basket"], hdr); PB.set_row(3, 32)
for i, r in enumerate(bk.itertuples(index=False), start=4):
    PB.write_row(i, 6, [r.order_number, r.orders, r.avg_basket_size, r.reorder_rate_pct], None)

def make_ch2():
    ch2 = wb.add_chart({"type": "line"})
    ch2.add_series({"name": "Repeat items, % of basket", "categories": ["Pivot_Basket", 5, 6, 3 + len(bk), 6],
                    "values": ["Pivot_Basket", 5, 9, 3 + len(bk), 9], "line": {"color": TEAL, "width": 3},
                    "marker": {"type": "circle", "size": 5, "fill": {"color": TEAL}, "border": {"color": "white"}}})
    ch2.set_title({"name": "Customers settle into a routine: repeat share of the basket triples", "name_font": {"size": 13, "bold": True, "color": INK}})
    ch2.set_x_axis({"name": "Customer's order number (1 = first order)", "name_font": {"size": 10, "bold": False}, "interval_unit": 4, "line": {"color": "#7F7F7F"}, "num_font": {"size": 10}})
    ch2.set_y_axis({"name": "% of basket that is a repeat item", "name_font": {"size": 10, "bold": False}, "min": 0, "max": 100, "major_unit": 20,
                    "num_format": '0"%"', "major_gridlines": {"visible": True, "line": {"color": "#D9D9D9"}}, "line": {"none": True}, "num_font": {"size": 10}})
    ch2.set_legend({"none": True}); ch2.set_size({"width": 760, "height": 400}); ch2.set_chartarea({"border": {"none": True}})
    return ch2

PB.insert_chart("L4", make_ch2())

# ------------------------------------------------------------------ Pivot_Dept_Repeat
PD.set_column("A:A", 20); PD.set_column("B:D", 16)
PD.write("A1", "Repeat-purchase rate by department", title)
PD.merge_range("A2:D2", "Repeat rate = share of items bought that the customer had bought before. Source: all 33.8M order lines.", note)
PD.write_row(3, 0, ["Department", "Items ordered", "Items reordered", "Repeat rate"], hdr); PD.set_row(3, 22)
for i, r in enumerate(dept.itertuples(index=False), start=4):
    PD.write(i, 0, r.department, txt); PD.write(i, 1, r.items_ordered, num); PD.write(i, 2, r.items_reordered, num)
    PD.write_formula(i, 3, f"=C{i+1}/B{i+1}", F(num_format="0.0%"), r.items_reordered / r.items_ordered)
last = 3 + len(dept)
PD.write(last + 2, 0, "Rate in % for chart", note)
pts = None
# chart works off a % column so labels read "67%"
PD.write(3, 5, "Repeat rate (%)", hdr)
for i, r in enumerate(dept.itertuples(index=False), start=4):
    PD.write_formula(i, 5, f"=D{i+1}*100", dec1, r.reorder_rate_pct)
def make_ch1():
    ch1 = wb.add_chart({"type": "bar"})
    ch1.add_series({"categories": ["Pivot_Dept_Repeat", 4, 0, last, 0], "values": ["Pivot_Dept_Repeat", 4, 5, last, 5], "fill": {"color": TEAL}, "gap": 45,
                    "data_labels": {"value": True, "num_format": '0"%"', "font": {"size": 10, "color": INK}}})
    ch1.set_title({"name": "Fresh staples get re-bought; pantry and personal care mostly do not", "name_font": {"size": 13, "bold": True, "color": INK}})
    ch1.set_y_axis({"reverse": True, "num_font": {"size": 10}, "line": {"color": "#7F7F7F"}})
    ch1.set_x_axis({"name": "% of items bought that were re-purchases", "name_font": {"size": 10, "bold": False}, "min": 0, "max": 100, "major_unit": 20,
                    "num_format": '0"%"', "major_gridlines": {"visible": True, "line": {"color": "#D9D9D9"}}, "line": {"none": True}, "num_font": {"size": 10}})
    ch1.set_legend({"none": True}); ch1.set_size({"width": 760, "height": 480}); ch1.set_chartarea({"border": {"none": True}})
    return ch1

PD.insert_chart("H4", make_ch1())
PD.merge_range(f"A{last+4}:D{last+6}", "Departments sorted by repeat rate. Above 60% = habit categories, under 45% = discovery categories.", note)

# ------------------------------------------------------------------ Pivot_Pairs
PP.set_column("A:B", 30); PP.set_column("C:E", 15)
PP.write("A1", "Products bought together", title)
PP.merge_range("A2:E2", "Based on a fixed random sample of 400,000 orders and the 300 most-bought products. Lift above 1 = bought together more often than chance.", note); PP.set_row(1, 32)
PP.write("A4", "Most frequent pairs (what to merchandise side by side)", h2)
PP.write_row(4, 0, ["Product A", "Product B", "Orders together", "% of all orders", "Lift"], hdr)
top = pairs.head(15)
for i, r in enumerate(top.itertuples(index=False), start=5):
    PP.write(i, 0, r.product_a, txt); PP.write(i, 1, r.product_b, txt); PP.write(i, 2, r.orders_together, num)
    PP.write_formula(i, 3, f"=C{i+1}/400000", F(num_format="0.00%"), r.orders_together / 400000); PP.write(i, 4, r.lift, dec2)
r0 = 5 + len(top) + 2
PP.write(r0, 0, "Strongest affinities (lift), pairs seen 800+ times (what to suggest at checkout)", h2)
PP.write_row(r0 + 1, 0, ["Product A", "Product B", "Orders together", "% of all orders", "Lift"], hdr)
aff = pairs[pairs.orders_together >= 800].sort_values("lift", ascending=False).head(10)
for i, r in enumerate(aff.itertuples(index=False), start=r0 + 2):
    PP.write(i, 0, r.product_a, txt); PP.write(i, 1, r.product_b, txt); PP.write(i, 2, r.orders_together, num)
    PP.write_formula(i, 3, f"=C{i+1}/400000", F(num_format="0.00%"), r.orders_together / 400000); PP.write(i, 4, r.lift, dec2)

# ------------------------------------------------------------------ Churn_Risk
PC.set_column("A:A", 30); PC.set_column("B:F", 17)
PC.write("A1", "Churn-risk signal and how well it predicts", title)
PC.merge_range("A2:F2", "High risk = latest gap between orders was 30+ days. Watch = regular shopper (usual gap under 12 days) now at 1.5x+ their own normal. The data has no calendar dates, so risk is judged from gaps between orders.", note); PC.set_row(1, 44)
PC.write("A4", "Customers by risk tier (latest order)", h2)
PC.write_row(4, 0, ["Risk tier", "Customers", "% of customers"], hdr)
order = ["High risk", "Watch", "Healthy"]; s = summary.set_index("risk_tier")
for i, t in enumerate(order, start=5):
    PC.write(i, 0, t, txt); PC.write(i, 1, int(s.loc[t, "customers"]), num)
    PC.write_formula(i, 2, f"=B{i+1}/SUM($B$6:$B$8)", F(num_format="0.0%"), s.loc[t, "customers"] / s.customers.sum())
PC.write("A11", "Back-test: rewind to each customer's 6th order, flag them, then see who faded", h2)
PC.write_row(11, 0, ["Shopper type", "Tier at order 6", "Customers", "% who faded", "Avg orders placed afterwards"], hdr); PC.set_row(11, 32)
back = back.assign(k=back.tier_at_order_6.map({"High risk": 0, "Watch": 1, "Healthy": 2})).sort_values(["cadence", "k"])
BT = {}
for i, r in enumerate(back.itertuples(index=False), start=12):
    PC.write(i, 0, r.cadence, txt); PC.write(i, 1, r.tier_at_order_6, txt); PC.write(i, 2, r.customers, num)
    PC.write(i, 3, r.pct_who_faded, pct1); PC.write(i, 4, r.avg_orders_placed_afterwards, dec1)
    BT[(r.cadence[:7], r.tier_at_order_6)] = (i, r.pct_who_faded)
PC.merge_range("A19:F21", "Faded = placed 2 or fewer further orders. Occasional shoppers are naturally less active, so each group is only compared with its own kind. Association, not proof of cause.", note)
rowR_hi, vR_hi = BT[("Regular", "High risk")]; rowR_ok, vR_ok = BT[("Regular", "Healthy")]
rowO_hi, vO_hi = BT[("Occasio", "High risk")]; rowO_ok, vO_ok = BT[("Occasio", "Healthy")]

# ------------------------------------------------------------------ Summary
S.set_column("A:A", 2); S.set_column("B:K", 11.5); S.set_column("L:L", 2)
S.merge_range("B2:K2", "Which customers are at risk of never ordering again, and which products keep people coming back?", F(bold=True, font_size=16, text_wrap=True))
S.set_row(1, 56)
S.merge_range("B3:K3", "Grocery order data (Instacart, 206,209 customers, 3.4M orders) used as a stand-in for quick-commerce. Three findings:", sub)

def finding(row, n, headline, text):
    S.merge_range(row, 1, row, 10, f"  FINDING {n}   {headline}", tag); S.set_row(row, 24)
    S.merge_range(row + 1, 1, row + 3, 10, text, body)

# Finding 1: number-backed
finding(4, 1, "A month of silence is the clearest warning sign",
        f"Regular shoppers who waited 30+ days between orders went on to fade ({vR_hi:.0f}% placed 2 or fewer more orders) about three times as often as those who kept their rhythm ({vR_ok:.0f}%). 31% of all customers have just had a 30+ day gap, so this is a big group worth a win-back nudge.")
S.merge_range("C9:E9", "", big_o); S.merge_range("G9:I9", "", big)
S.write_formula("C9", f"=Churn_Risk!D{rowR_hi+1}", big_o, vR_hi); S.write_formula("G9", f"=Churn_Risk!D{rowR_ok+1}", big, vR_ok)
S.set_row(8, 46)
S.merge_range("C10:E10", "faded after a 30+ day gap (regular shoppers)", cap); S.merge_range("G10:I10", "faded when rhythm was kept", cap); S.set_row(9, 30)

# Finding 2: chart 1
d = dept.set_index("department"); sq = lift.set_index("product_name").loc["Organic Strawberries"]
finding(11, 2, "Fresh everyday foods are what bring people back",
        f"Dairy & eggs ({d.loc['dairy eggs','reorder_rate_pct']:.0f}%) and produce ({d.loc['produce','reorder_rate_pct']:.0f}%) are re-bought about two-thirds of the time, versus pantry ({d.loc['pantry','reorder_rate_pct']:.0f}%) and personal care ({d.loc['personal care','reorder_rate_pct']:.0f}%). "
        f"New customers whose first basket included Organic Strawberries became loyal {sq.pct_became_loyal:.0f}% of the time, against {sq.baseline_pct_loyal:.0f}% overall.")
S.insert_chart("B17", make_ch1(), {"x_offset": 4, "y_offset": 4, "x_scale": 0.9, "y_scale": 0.9})

# Finding 3: chart 2
r30 = bk[bk.order_number == 30].iloc[0]; r2 = bk[bk.order_number == 2].iloc[0]
finding(40, 3, "Baskets do not grow, they harden into a routine",
        f"Average basket size stays near {bk.avg_basket_size.mean():.0f} items from a customer's 1st order to their 30th. What changes is how much of it is repeat items: {r2.reorder_rate_pct:.0f}% on the 2nd order, {r30.reorder_rate_pct:.0f}% by the 30th. "
        f"Retention is about locking in the repeat items, not selling more items.")
S.insert_chart("B46", make_ch2(), {"x_offset": 4, "y_offset": 4, "x_scale": 0.9, "y_scale": 0.95})
S.merge_range("B69:K71", "Limits: the data is US weekly-grocery behaviour with no calendar dates and every customer has 4+ orders, so 'at risk' is inferred from gaps between orders and 'faded' means few further orders. "
              "Quick-commerce customers order more often, so gap thresholds would need re-tuning.", note)
S.set_landscape(); S.fit_to_pages(1, 0)
wb.close(); print("wrote", root / "excel" / "Instacart_Basket_Analysis.xlsx")
