-- Fixture for W025 assertion-malformed.
-- sql-sop defines a small predicate grammar for `-- @assert:` comments.
-- Each block below shows the kind of malformed predicate W025 fires on.
-- Well-formed cases live in the unit tests, not here.

-- W025: predicate is just a bare identifier, no operator
-- @assert: row_count

-- W025: numeric operator with non-numeric right-hand side
-- @assert: row_count > zero

-- W025: unique() form without parentheses
-- @assert: unique batch_id

-- W025: freeform prose in place of a predicate
-- @assert: weight is positive
