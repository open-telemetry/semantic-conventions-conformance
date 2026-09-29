-- Copyright The OpenTelemetry Authors
-- SPDX-License-Identifier: Apache-2.0

DROP KEYSPACE IF EXISTS conformance;

CREATE KEYSPACE conformance
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

CREATE TABLE conformance.items (
    id int PRIMARY KEY,
    name text
);
