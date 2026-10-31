-- Schema for classified activity (docs/CONTRACTS.md, section 6).
-- Runs once, when the Postgres volume is first created.

CREATE TABLE predictions (
  id          BIGSERIAL PRIMARY KEY,
  device_id   TEXT        NOT NULL,
  ts          TIMESTAMPTZ NOT NULL,
  activity    TEXT        NOT NULL,
  confidence  REAL        NOT NULL
);

CREATE INDEX predictions_device_ts ON predictions (device_id, ts DESC);
