-- Test fixture: all error rules should trigger

-- E001: DELETE without WHERE
DELETE FROM orders;

-- E002: DROP without IF EXISTS
DROP TABLE users;

-- E003: GRANT in application code
GRANT SELECT ON users TO public;

-- E004: String concatenation in WHERE
SELECT * FROM users WHERE name = '' + @input + '';

-- E005: INSERT without column list
INSERT INTO orders VALUES (1, 'test', 100);

-- E006: UPDATE without WHERE
UPDATE orders SET status = 'cancelled';

-- E009: UPDATE FROM with comma-separated tables (T-SQL legacy implicit join)
UPDATE customers SET status = o.status FROM customers c, orders o WHERE c.customer_id = o.customer_id;
