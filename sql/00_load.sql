-- Load the six Instacart CSVs into DuckDB and build the two base tables used everywhere else.
CREATE OR REPLACE TABLE orders      AS SELECT * FROM read_csv_auto('raw/orders.csv');
CREATE OR REPLACE TABLE products    AS SELECT * FROM read_csv_auto('raw/products.csv');
CREATE OR REPLACE TABLE aisles      AS SELECT * FROM read_csv_auto('raw/aisles.csv');
CREATE OR REPLACE TABLE departments AS SELECT * FROM read_csv_auto('raw/departments.csv');
-- "prior" = every order except each customer's last; "train" = last order for a subset of customers.
-- ("test" last orders have no product detail in the public data, so they are excluded from basket work.)
CREATE OR REPLACE TABLE order_items AS
  SELECT * FROM read_csv_auto('raw/order_products__prior.csv')
  UNION ALL
  SELECT * FROM read_csv_auto('raw/order_products__train.csv');
