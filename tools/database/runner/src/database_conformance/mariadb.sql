-- Copyright The OpenTelemetry Authors
-- SPDX-License-Identifier: Apache-2.0

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

DELIMITER //

CREATE OR REPLACE PROCEDURE noop()
BEGIN
END//

DELIMITER ;
