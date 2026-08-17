// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * The HTTP conformance exchanges, as Node reads them.
 *
 * Read from `tools/http/test-client/contract.json` — the one place the traffic
 * is written down, so a Node scenario and a scenario in any other language are
 * measured against the same requests.
 *
 * Every framework shares the answers here rather than restating them, while a
 * server scenario declares its routes in its own framework's native form.
 */

const fs = require("node:fs");
const path = require("node:path");

const { ContractError } = require("./contract-error");

/** Every route answers JSON, so a scenario has one content type rather than a rule per route. */
const CONTENT_TYPE = "application/json";

/**
 * Fixed rather than the HTTP library's default, so a server scenario sees the
 * same client whichever language sent the requests.
 */
const USER_AGENT = "otel-http-conformance/1";

/**
 * Where `contract.json` is: beside this package in a checkout, or — once npm
 * has installed this package as a copy in a dependency tree — at its place in
 * the repository above that tree.
 *
 * Searched for rather than packaged, unlike the Python wheel and the Java jar,
 * which each carry a copy: npm packs a package's own directory and has no way
 * to reach outside it, so a copy would have to be generated into the source
 * tree first. One lookup that walks up is less machinery than that.
 */
function contractPath() {
  const beside = path.join(__dirname, "..", "..", "contract.json");
  if (fs.existsSync(beside)) {
    return beside;
  }
  let directory = __dirname;
  for (;;) {
    const candidate = path.join(
      directory,
      "tools",
      "http",
      "test-client",
      "contract.json",
    );
    if (fs.existsSync(candidate)) {
      return candidate;
    }
    const parent = path.dirname(directory);
    if (parent === directory) {
      throw new Error(`no contract.json at or above ${__dirname}`);
    }
    directory = parent;
  }
}

const CONTRACT = contractPath();

const EXCHANGES = Object.freeze(
  JSON.parse(fs.readFileSync(CONTRACT, "utf8")).requests.map((entry) =>
    Object.freeze({
      method: entry.method,
      path: entry.path,
      // null rather than absent, so a sender has one shape to check.
      body: entry.body ?? null,
      status: entry.status,
      responseBody: entry.responseBody,
      readiness: entry.readiness ?? false,
      // What the request is in the sequence for. Carried as data rather than
      // as a comment so every language reading the contract has it too.
      description: entry.description,
    }),
  ),
);

/** Every exchange the contract describes, including readiness, in order. */
function exchanges() {
  return EXCHANGES;
}

/** The measured requests to send, in order. */
function requests() {
  return EXCHANGES.filter((exchange) => !exchange.readiness);
}

function withoutQuery(target) {
  return target.split("?", 1)[0];
}

/** The exchange answering `method path`, if the contract describes one. */
function exchangeFor(method, target) {
  const concrete = withoutQuery(target);
  return (
    EXCHANGES.find(
      (exchange) =>
        exchange.method === method && withoutQuery(exchange.path) === concrete,
    ) ?? null
  );
}

/** An exchange's response body with the request body inserted. */
function renderResponseBody(exchange, requestBody) {
  // A function rather than the body itself: a string replacement reads `$&`
  // and its siblings as substitution patterns, so a body carrying one would be
  // echoed differently here than by the Java and Python readers, which both
  // substitute literally.
  return exchange.responseBody.replace("${requestBody}", () =>
    requestBody ? requestBody : "{}",
  );
}

/**
 * Parses `json`, so two bodies compare by structure rather than by spacing.
 *
 * A body that is not JSON is a contract failure rather than a crash: it is the
 * server answering something the contract does not describe.
 */
function parse(json) {
  try {
    return JSON.parse(json);
  } catch (error) {
    throw new ContractError(`not JSON: ${json}`, { cause: error });
  }
}

module.exports = {
  CONTENT_TYPE,
  CONTRACT,
  USER_AGENT,
  exchangeFor,
  exchanges,
  parse,
  renderResponseBody,
  requests,
};
