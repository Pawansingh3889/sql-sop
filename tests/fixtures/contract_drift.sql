-- End-to-end fixture for the contract rules pack (C001-C005).
--
-- Each statement deliberately violates one rule. The integration test
-- in test_contracts.py runs the entire fixture against the sample
-- contract (tests/fixtures/contract_sample.yml) and asserts every
-- rule fires exactly once.

-- C001 column-not-in-contract: orders has no 'bogus_column' field.
SELECT o.bogus_column
FROM orders o;

-- C002 table-not-in-contract: ghost_table is not in the contract.
SELECT *
FROM ghost_table;

-- C003 not-null-violation: orders requires customer_id and created_at.
INSERT INTO orders (total)
VALUES (99.99);

-- C004 primary-key-missing-on-insert: 'audit_log' has a no-default PK.
-- See test_contracts.py for the contract used (built inline because the
-- shared sample contract gives orders.id has_default=true).
-- Placeholder query for visual continuity; the C004 test uses an
-- inline contract.
INSERT INTO audit_log (msg)
VALUES ('something happened');

-- C005 unmapped-fk: orders.id is not a foreign key to customers.id.
SELECT *
FROM orders o
JOIN customers c ON o.id = c.id;
