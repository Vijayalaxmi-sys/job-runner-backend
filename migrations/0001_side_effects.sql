-- PROVIDED — our grading harness reads this table.
--
-- You may ADD constraints and indexes to it from your own migrations.
-- You may NOT rename the table or its columns, or change their types.
--
-- Every other table in this system is yours to design. Put your DDL in
-- new files: migrations/0002_*.sql, 0003_*.sql, ... They are applied in
-- filename order and each file runs exactly once.

CREATE TABLE IF NOT EXISTS side_effects (
    id         BIGSERIAL   PRIMARY KEY,
    job_id     UUID        NOT NULL,
    payload    JSONB       NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
