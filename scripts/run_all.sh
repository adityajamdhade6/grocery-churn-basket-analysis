#!/usr/bin/env bash
# Rebuilds everything from the raw CSVs. Usage (from the project root): bash scripts/run_all.sh
# Needs: unzip archive.zip into ./raw first, and `pip install -r requirements.txt`
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -c "import duckdb" 2>/dev/null || { echo "pip install -r requirements.txt first"; exit 1; }
mkdir -p data results excel dashboard
python3 -c "import duckdb; duckdb.connect('data/instacart.duckdb').execute(open('sql/00_load.sql').read())"
python3 scripts/run_sql.py 01_churn_risk.sql 02_retention_products.sql 03_basket.sql
python3 scripts/build_excel.py
python3 scripts/build_dashboard.py
# fallback copy without the injected PivotTable parts, then attach the PivotTables to the main workbook
cp excel/Instacart_Basket_Analysis.xlsx excel/Instacart_Basket_Analysis_no_pivot_objects.xlsx
python3 scripts/add_pivots.py
