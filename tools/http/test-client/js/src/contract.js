// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/** The HTTP conformance exchanges supplied by the runner as JSON. */

/** Every route answers JSON, so a scenario has one content type rather than a rule per route. */
const CONTENT_TYPE = "application/json";

/**
 * Fixed rather than the HTTP library's default, so a server scenario sees the
 * same client whichever language sent the requests.
 */
const USER_AGENT = "otel-http-conformance/1";
const ACTION_VARIABLE = "OTEL_CONFORMANCE_SCENARIO_ACTION";
const ACTIONS_VARIABLE = "OTEL_CONFORMANCE_SCENARIO_ACTIONS";

function parseJson(raw, variable) {
  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error(`${variable} contains malformed JSON: ${error.message}`, {
      cause: error,
    });
  }
}

function checkKeys(value, allowed, where) {
  const unknown = Object.keys(value).filter((key) => !allowed.has(key));
  if (unknown.length) {
    throw new Error(
      `${where} has unknown field(s): ${unknown.sort().join(", ")}`,
    );
  }
}

function actionExchange(value, variable, readiness) {
  const where = `${variable} action`;
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${where} must be a JSON object`);
  }
  checkKeys(value, new Set(["request", "response"]), where);
  if (!("request" in value) || !("response" in value)) {
    throw new Error(`${where} requires request and response objects`);
  }
  for (const field of ["request", "response"]) {
    if (
      value[field] === null ||
      typeof value[field] !== "object" ||
      Array.isArray(value[field])
    ) {
      throw new Error(`${where}.${field} must be a JSON object`);
    }
  }

  const request = value.request;
  const response = value.response;
  checkKeys(request, new Set(["method", "path", "body"]), `${where}.request`);
  checkKeys(response, new Set(["status", "body"]), `${where}.response`);
  if (typeof request.method !== "string" || request.method.length === 0) {
    throw new Error(`${where}.request.method must be a non-empty string`);
  }
  if (typeof request.path !== "string" || !request.path.startsWith("/")) {
    throw new Error(`${where}.request.path must start with '/'`);
  }
  if (
    request.body !== undefined &&
    request.body !== null &&
    typeof request.body !== "string"
  ) {
    throw new Error(`${where}.request.body must be a string`);
  }
  if (
    !Number.isInteger(response.status) ||
    response.status < 100 ||
    response.status > 599
  ) {
    throw new Error(`${where}.response.status must be an HTTP status`);
  }
  if (typeof response.body !== "string") {
    throw new Error(`${where}.response.body must be a string`);
  }
  return Object.freeze({
    method: request.method,
    path: request.path,
    body: request.body ?? null,
    status: response.status,
    responseBody: response.body,
    readiness,
    description: readiness ? "runner readiness action" : "runner action",
  });
}

/** Every exchange the runner supplied, including readiness, in order. */
function exchanges(raw = process.env[ACTIONS_VARIABLE]) {
  if (raw === undefined) {
    throw new Error(`${ACTIONS_VARIABLE} is not set`);
  }
  const actions = parseJson(raw, ACTIONS_VARIABLE);
  if (!Array.isArray(actions) || actions.length === 0) {
    throw new Error(
      `${ACTIONS_VARIABLE} must be a non-empty JSON array of actions`,
    );
  }
  return Object.freeze(
    actions.map((action, index) =>
      actionExchange(action, `${ACTIONS_VARIABLE}[${index}]`, index === 0),
    ),
  );
}

/** The measured requests supplied by the runner. */
function requests(raw = process.env[ACTIONS_VARIABLE]) {
  return Object.freeze(exchanges(raw).slice(1));
}

/** The one request selected by the runner. */
function scenarioRequest(raw = process.env[ACTION_VARIABLE]) {
  if (raw === undefined) {
    throw new Error(`${ACTION_VARIABLE} is not set`);
  }
  return actionExchange(
    parseJson(raw, ACTION_VARIABLE),
    ACTION_VARIABLE,
    false,
  );
}

function withoutQuery(target) {
  return target.split("?", 1)[0];
}

/** The exchange answering `method path`, if the runner supplied one. */
function exchangeFor(method, target) {
  const concrete = withoutQuery(target);
  return (
    exchanges().find(
      (exchange) =>
        exchange.method === method && withoutQuery(exchange.path) === concrete,
    ) ?? null
  );
}

/** An exchange's response body with the request body inserted. */
function renderResponseBody(exchange, requestBody) {
  return exchange.responseBody.replace("${requestBody}", () =>
    requestBody ? requestBody : "{}",
  );
}

module.exports = {
  ACTIONS_VARIABLE,
  ACTION_VARIABLE,
  CONTENT_TYPE,
  USER_AGENT,
  exchangeFor,
  exchanges,
  renderResponseBody,
  requests,
  scenarioRequest,
};
