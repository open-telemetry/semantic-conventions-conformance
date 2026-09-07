// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const http = require("node:http");
const path = require("node:path");
const test = require("node:test");
const { URL } = require("node:url");

const grpc = require("@grpc/grpc-js");
const { respond } = require("@otel-conformance/http-test-client");

const TRACE_EXPORT_PATH =
  "/opentelemetry.proto.collector.trace.v1.TraceService/Export";

const service = {
  export: {
    path: TRACE_EXPORT_PATH,
    requestStream: false,
    responseStream: false,
    requestSerialize: (value) => value,
    requestDeserialize: (value) => value,
    responseSerialize: (value) => value,
    responseDeserialize: (value) => value,
  },
};

function listen(server) {
  return new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
}

function close(server) {
  server.closeAllConnections?.();
  return new Promise((resolve) => server.close(resolve));
}

function bind(server) {
  return new Promise((resolve, reject) => {
    server.bindAsync(
      "127.0.0.1:0",
      grpc.ServerCredentials.createInsecure(),
      (error, port) => (error ? reject(error) : resolve(port)),
    );
  });
}

function run(environment) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ["client.js"], {
      cwd: path.resolve(__dirname, ".."),
      env: { ...process.env, ...environment },
      stdio: "inherit",
    });
    child.once("error", reject);
    child.once("exit", (code) =>
      code === 0 ? resolve() : reject(new Error(`scenario exited ${code}`)),
    );
  });
}

function varint(buffer, offset) {
  let value = 0;
  let shift = 0;
  for (;;) {
    const byte = buffer[offset++];
    value += (byte & 0x7f) * 2 ** shift;
    if ((byte & 0x80) === 0) {
      return { offset, value };
    }
    shift += 7;
  }
}

function fields(buffer) {
  const result = [];
  let offset = 0;
  while (offset < buffer.length) {
    const key = varint(buffer, offset);
    offset = key.offset;
    const wireType = key.value & 7;
    const number = key.value >> 3;
    if (wireType === 0) {
      const value = varint(buffer, offset);
      result.push({ number, value: value.value, wireType });
      offset = value.offset;
      continue;
    }
    if (wireType === 2) {
      const size = varint(buffer, offset);
      offset = size.offset;
      result.push({
        number,
        value: buffer.subarray(offset, offset + size.value),
        wireType,
      });
      offset += size.value;
      continue;
    }
    if (wireType === 1 || wireType === 5) {
      const size = wireType === 1 ? 8 : 4;
      result.push({
        number,
        value: buffer.subarray(offset, offset + size),
        wireType,
      });
      offset += size;
      continue;
    }
    throw new Error(`unsupported protobuf wire type ${wireType}`);
  }
  return result;
}

function first(fieldsList, number, wireType) {
  return fieldsList.find(
    (field) => field.number === number && field.wireType === wireType,
  )?.value;
}

function all(fieldsList, number, wireType) {
  return fieldsList
    .filter((field) => field.number === number && field.wireType === wireType)
    .map((field) => field.value);
}

function text(value) {
  return value.toString("utf8");
}

function attribute(value) {
  const keyValue = fields(value);
  const key = text(first(keyValue, 1, 2));
  const anyValue = fields(first(keyValue, 2, 2));
  const raw = first(anyValue, 1, 2) ?? first(anyValue, 3, 0);
  return [key, Buffer.isBuffer(raw) ? text(raw) : raw];
}

function decodeSpans(payload) {
  return all(fields(payload), 1, 2).flatMap((resourceSpans) =>
    all(fields(resourceSpans), 2, 2).flatMap((scopeSpans) =>
      all(fields(scopeSpans), 2, 2).map((encoded) => {
        const span = fields(encoded);
        return {
          attributes: new Map(all(span, 9, 2).map(attribute)),
          kind: first(span, 6, 0),
          name: text(first(span, 5, 2)),
        };
      }),
    ),
  );
}

test("measures only the selected browser Fetch request", async () => {
  const mock = http.createServer(async (request, response) => {
    const chunks = [];
    for await (const chunk of request) {
      chunks.push(chunk);
    }
    const body = chunks.length ? Buffer.concat(chunks).toString("utf8") : null;
    const answer = respond(
      request.method,
      new URL(request.url, "http://unused").pathname,
      body,
    );
    response.writeHead(answer.status, {
      "content-type": "application/json",
    });
    response.end(answer.body);
  });
  await listen(mock);

  const exports = [];
  const collector = new grpc.Server();
  collector.addService(service, {
    export(call, callback) {
      exports.push(call.request);
      callback(null, Buffer.alloc(0));
    },
  });
  const collectorPort = await bind(collector);
  collector.start();

  try {
    await run({
      MOCK_SERVER_URL: `http://127.0.0.1:${mock.address().port}`,
      OTEL_CONFORMANCE_SCENARIO_INDEX: "2",
      OTEL_EXPORTER_OTLP_ENDPOINT: `http://127.0.0.1:${collectorPort}`,
    });
  } finally {
    await close(mock);
    collector.forceShutdown();
  }
  const spans = exports.flatMap(decodeSpans);
  assert.equal(spans.length, 1, "the exporter request must not create a span");
  assert.deepEqual(
    spans.map(({ attributes, kind, name }) => {
      const url = new URL(attributes.get("url.full"));
      return {
        kind,
        method: attributes.get("http.request.method"),
        name,
        path: `${url.pathname}${url.search}`,
        status: attributes.get("http.response.status_code"),
      };
    }),
    [
      {
        kind: 3,
        method: "POST",
        name: "POST",
        path: "/items",
        status: 201,
      },
    ],
  );
});
