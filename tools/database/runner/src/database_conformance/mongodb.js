// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const conformance = db.getSiblingDB("conformance");

conformance.createUser({
  user: "conformance",
  pwd: "conformance",
  roles: [{role: "readWrite", db: "conformance"}],
});
conformance.items.drop();
conformance.createCollection("items");
conformance.items.insertMany([
  {_id: "find", name: "find"},
  {_id: "update", name: "before"},
  {_id: "delete", name: "delete"},
  {_id: "aggregate", name: "aggregate"},
]);
