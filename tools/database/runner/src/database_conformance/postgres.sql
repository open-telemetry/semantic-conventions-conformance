-- Copyright The OpenTelemetry Authors
-- SPDX-License-Identifier: Apache-2.0

CREATE SCHEMA IF NOT EXISTS conformance;

CREATE TABLE IF NOT EXISTS conformance.items (
    id integer PRIMARY KEY,
    name text NOT NULL
);

CREATE OR REPLACE PROCEDURE conformance.noop()
LANGUAGE plpgsql
AS $$
BEGIN
    NULL;
END;
$$;
