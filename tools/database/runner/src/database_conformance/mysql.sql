-- Copyright The OpenTelemetry Authors
-- SPDX-License-Identifier: Apache-2.0

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

DROP PROCEDURE IF EXISTS noop;

DELIMITER //

CREATE PROCEDURE noop()
BEGIN
END//

DELIMITER ;
