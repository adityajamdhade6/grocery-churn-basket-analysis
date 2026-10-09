"""Run the SQL files in order against DuckDB.
A statement tagged `-- @export name` also gets written to results/name.csv
(for CREATE TABLE statements, the created table is exported)."""
import re, sys, duckdb
from pathlib import Path

root = Path(__file__).resolve().parent.parent
con = duckdb.connect(str(root / "data" / "instacart.duckdb"))
files = sys.argv[1:] or sorted(p.name for p in (root / "sql").glob("*.sql"))
for name in files:
    for stmt in re.split(r";[ \t]*\n", (root / "sql" / name).read_text()):
        if not re.sub(r"--.*", "", stmt).strip():
            continue
        tag = re.search(r"-- @export (\w+)", stmt)
        created = re.search(r"CREATE OR REPLACE TABLE (\w+)", stmt)
        if created:
            con.execute(stmt)
            df = con.execute(f"SELECT * FROM {created.group(1)}").df() if tag else None
        else:
            df = con.execute(stmt).df() if tag else (con.execute(stmt), None)[1]
        if tag:
            df.to_csv(root / "results" / f"{tag.group(1)}.csv", index=False)
            print(f"{name}: exported {tag.group(1)} ({len(df):,} rows)")
