// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * The HTTP conformance exchanges, as Node reads them.
 *
 * Read from `tools/http/test-client/contract.yaml` — the one place the traffic
 * is written down, so a Node scenario and a scenario in any other language are
 * measured against the same requests.
 *
 * Every framework shares the answers here rather than restating them, while a
 * server scenario declares its routes in its own framework's native form.
 */

const fs = require("node:fs");
const path = require("node:path");
const YAML = require("yaml");
const { ContractError } = require("./contract-error");

/** Every route answers JSON, so a scenario has one content type rather than a rule per route. */
const CONTENT_TYPE = "application/json";

/**
 * Fixed rather than the HTTP library's default, so a server scenario sees the
 * same client whichever language sent the requests.
 */
const USER_AGENT = "otel-http-conformance/1";
const SCENARIO_INDEX_VARIABLE = "OTEL_CONFORMANCE_SCENARIO_INDEX";

/**
 * Where `contract.yaml` is: beside this package in a checkout, or — once npm
 * has installed this package as a copy in a dependency tree — at its place in
 * the repository above that tree.
 *
 * Searched for rather than packaged: npm packs a package's own directory and
 * has no way to reach outside it, so a copy would have to be generated into
 * the source tree first. One lookup that walks up is less machinery than that.
 */
function contractPath() {
  const beside = path.join(__dirname, "..", "..", "contract.yaml");
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
      "contract.yaml",
    );
    if (fs.existsSync(candidate)) {
      return candidate;
    }
    const parent = path.dirname(directory);
    if (parent === directory) {
      throw new Error(`no contract.yaml at or above ${__dirname}`);
    }
    directory = parent;
  }
}

const CONTRACT = contractPath();

const DOCUMENT = YAML.parse(fs.readFileSync(CONTRACT, "utf8"));

function exchange(entry, readiness) {
  return Object.freeze({
    method: entry.action.request.method,
    path: entry.action.request.path,
    // null rather than absent, so a sender has one shape to check.
    body: entry.action.request.body ?? null,
    status: entry.action.response.status,
    responseBody: entry.action.response.body,
    readiness,
    description: entry.description,
  });
}

const REQUESTS = Object.freeze(
  DOCUMENT.scenarios.map((entry) => exchange(entry, false)),
);

const READINESS = exchange(DOCUMENT.readiness, true);

const EXCHANGES = Object.freeze([READINESS, ...REQUESTS]);

/** Every exchange the contract describes, including readiness, in order. */
function exchanges() {
  return EXCHANGES;
}

/** The measured requests to send, in order. */
function requests() {
  return REQUESTS;
}

/** The one request selected by the runner's zero-based contract index. */
function scenarioRequest(index = process.env[SCENARIO_INDEX_VARIABLE]) {
  if (typeof index === "number") {
    index = String(index);
  }
  if (typeof index !== "string" || !/^(0|[1-9]\d*)$/.test(index)) {
    throw new Error(
      `${SCENARIO_INDEX_VARIABLE} must be a zero-based decimal index, got ${JSON.stringify(index)}`,
    );
  }
  const exchange = REQUESTS[Number(index)];
  if (exchange === undefined) {
    throw new Error(
      `${SCENARIO_INDEX_VARIABLE}=${index} selects no contract entry; ` +
        `expected 0..${REQUESTS.length - 1}`,
    );
  }
  return exchange;
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
  // and its siblings as substitution patterns, so a body carrying one would
  // not be echoed literally.
  return exchange.responseBody.replace("${requestBody}", () =>
    requestBody ? requestBody : "{}",
  );
}

/** Check one answer against the request's expected status and JSON body. */
function verify(exchange, status, body) {
  if (status !== exchange.status) {
    throw new ContractError(
      `${exchange.method} ${exchange.path} answered ${status}, ` +
        `expected ${exchange.status}`,
    );
  }
  let actual;
  let expected;
  try {
    actual = JSON.parse(body);
    expected = JSON.parse(renderResponseBody(exchange, exchange.body));
  } catch (error) {
    throw new ContractError(
      `${exchange.method} ${exchange.path} did not return the expected JSON`,
      { cause: error },
    );
  }
  if (!require("node:util").isDeepStrictEqual(actual, expected)) {
    throw new ContractError(
      `${exchange.method} ${exchange.path} answered ${JSON.stringify(actual)}, ` +
        `expected ${JSON.stringify(expected)}`,
    );
  }
}

module.exports = {
  CONTENT_TYPE,
  CONTRACT,
  SCENARIO_INDEX_VARIABLE,
  USER_AGENT,
  exchangeFor,
  exchanges,
  renderResponseBody,
  requests,
  scenarioRequest,
  verify,
};
