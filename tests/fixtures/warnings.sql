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


-- W013: OVER without PARTITION BY
SELECT
  user_id,
  ROW_NUMBER() OVER () AS rn
FROM events;


-- W016: NOT IN with subquery
SELECT *
FROM customers
WHERE id NOT IN (SELECT customer_id FROM orders);

-- W015: Function on column in JOIN ... ON
SELECT *
FROM orders o
JOIN customers c ON UPPER(o.email) = UPPER(c.email);
