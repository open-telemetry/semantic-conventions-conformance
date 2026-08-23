// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

function send(method, url, body) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open(method, url);
    if (body !== null) {
      request.setRequestHeader("content-type", "application/json");
    }
    request.onload = () =>
      resolve({ status: request.status, body: request.responseText });
    request.onerror = () =>
      reject(new Error(`XMLHttpRequest failed for ${method} ${url}`));
    request.send(body);
  });
}

module.exports = { send };
