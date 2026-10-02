-- Copyright The OpenTelemetry Authors
-- SPDX-License-Identifier: Apache-2.0

IF DB_ID(N'conformance') IS NULL
BEGIN
    CREATE DATABASE [conformance];
END;
GO

USE [conformance];
GO

IF SCHEMA_ID(N'conformance') IS NULL
BEGIN
    EXEC(N'CREATE SCHEMA [conformance]');
END;
GO

IF OBJECT_ID(N'conformance.items', N'U') IS NULL
BEGIN
    CREATE TABLE [conformance].[items] (
        [id] INTEGER NOT NULL PRIMARY KEY,
        [name] NVARCHAR(255) NOT NULL
    );
END;
GO

CREATE OR ALTER PROCEDURE [conformance].[noop]
AS
BEGIN
    SET NOCOUNT ON;
END;
GO
