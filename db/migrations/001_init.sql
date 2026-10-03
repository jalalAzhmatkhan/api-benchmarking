-- Benchmark schema. Spec: Documentation/specs/database-schema.md
-- Only the primary-key index; no secondary indexes, triggers or extensions.
CREATE TABLE items (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         VARCHAR(100)  NOT NULL CHECK (char_length(name) >= 1),
    description  VARCHAR(1000) NULL,
    price_cents  BIGINT        NOT NULL CHECK (price_cents >= 0),
    quantity     INTEGER       NOT NULL CHECK (quantity >= 0),
    created_at   TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ   NOT NULL DEFAULT now()
);
