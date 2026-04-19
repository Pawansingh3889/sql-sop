-- Test fixture: warning rules should trigger

-- W001: SELECT *
SELECT * FROM users;

-- W003: Function on column in WHERE
SELECT id FROM orders WHERE YEAR(created_at) = 2024;

-- W007: Hardcoded values
SELECT id FROM orders WHERE amount > 10000;

-- W010: Commented-out code
-- SELECT * FROM deleted_users;

-- W011: UNION without ALL
SELECT id FROM orders_2024
UNION
SELECT id FROM orders_2025;

-- W012: GROUP BY by ordinal
SELECT region, status, COUNT(*)
FROM orders
GROUP BY 1, 2;

-- W013: OVER without ORDER BY / PARTITION BY - failing case
SELECT
  user_id,
  ROW_NUMBER() OVER () AS rn
FROM events;

