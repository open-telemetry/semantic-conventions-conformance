/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package io.opentelemetry.conformance.http;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;

/** The request contract shared by Java HTTP client and server conformance scenarios. */
public final class HttpTestClient {
  private static final Duration CONNECT_TIMEOUT = Duration.ofSeconds(1);
  private static final Duration REQUEST_TIMEOUT = Duration.ofSeconds(10);
  private static final Duration HEALTH_RETRY = Duration.ofMillis(50);

  public static final List<Request> REQUESTS =
      List.of(
          new Request("GET", "/users/123", null),
          new Request("GET", "/users/123?fields=name&verbose=true", null),
          new Request("POST", "/items", "{\"name\":\"widget\"}"),
          new Request("GET", "/status/404", null),
          new Request("GET", "/status/500", null));

  private HttpTestClient() {}

  /** Sends one request using the HTTP client library under test. */
  @FunctionalInterface
  public interface Sender {
    Response send(String method, String url, String body) throws Exception;
  }

  public record Request(String method, String path, String body) {}

  public record Response(int statusCode, String body) {}

  /** Waits for health, then sends the shared request sequence through {@code sender}. */
  public static void drive(String baseUrl, Sender sender) throws Exception {
    requireUrl(baseUrl);
    waitForHealth(baseUrl);
    for (Request request : REQUESTS) {
      Response response =
          sender.send(request.method(), baseUrl + request.path(), request.body());
      System.out.printf(
          "%s %s -> %d %s%n",
          request.method(),
          request.path(),
          response.statusCode(),
          abbreviate(response.body()));
    }
  }

  /** Waits for {@code /health} using an uninstrumented raw HTTP/1.1 socket. */
  public static void waitForHealth(String baseUrl) throws Exception {
    long deadline = System.nanoTime() + REQUEST_TIMEOUT.toNanos();
    Exception lastFailure = null;
    while (System.nanoTime() < deadline) {
      try {
        Response response = rawRequest("GET", baseUrl + "/health", null);
        if (response.statusCode() >= 200 && response.statusCode() < 300) {
          return;
        }
        lastFailure =
            new IOException("/health returned HTTP " + response.statusCode());
      } catch (IOException exception) {
        lastFailure = exception;
      }
      Thread.sleep(HEALTH_RETRY.toMillis());
    }
    throw new IOException(
        "the scenario server did not answer " + baseUrl + "/health within 10 seconds",
        lastFailure);
  }

  /** Sends a request without using an HTTP client API that a Java agent could instrument. */
  public static Response rawRequest(String method, String url, String body)
      throws IOException {
    URI uri = URI.create(url);
    if (!"http".equals(uri.getScheme()) || uri.getHost() == null) {
      throw new IllegalArgumentException("raw HTTP test requests require an http:// URL: " + url);
    }

    int port = uri.getPort() == -1 ? 80 : uri.getPort();
    String target = uri.getRawPath();
    if (target == null || target.isEmpty()) {
      target = "/";
    }
    if (uri.getRawQuery() != null) {
      target += "?" + uri.getRawQuery();
    }

    byte[] content =
        body == null ? new byte[0] : body.getBytes(StandardCharsets.UTF_8);
    try (Socket socket = new Socket()) {
      socket.connect(
          new InetSocketAddress(uri.getHost(), port),
          Math.toIntExact(CONNECT_TIMEOUT.toMillis()));
      socket.setSoTimeout(Math.toIntExact(REQUEST_TIMEOUT.toMillis()));

      OutputStream output = socket.getOutputStream();
      StringBuilder headers =
          new StringBuilder()
              .append(method)
              .append(' ')
              .append(target)
              .append(" HTTP/1.1\r\nHost: ")
              .append(uri.getHost())
              .append(':')
              .append(port)
              .append("\r\nConnection: close\r\n");
      if (body != null) {
        headers
            .append("Content-Type: application/json\r\nContent-Length: ")
            .append(content.length)
            .append("\r\n");
      }
      headers.append("\r\n");
      output.write(headers.toString().getBytes(StandardCharsets.US_ASCII));
      output.write(content);
      output.flush();

      byte[] response = readAll(socket.getInputStream());
      return parseResponse(response);
    }
  }

  private static byte[] readAll(InputStream input) throws IOException {
    ByteArrayOutputStream output = new ByteArrayOutputStream();
    input.transferTo(output);
    return output.toByteArray();
  }

  private static Response parseResponse(byte[] response) throws IOException {
    String text = new String(response, StandardCharsets.UTF_8);
    int firstLineEnd = text.indexOf("\r\n");
    int headersEnd = text.indexOf("\r\n\r\n");
    if (firstLineEnd < 0 || headersEnd < 0) {
      throw new IOException("invalid HTTP response");
    }

    String[] statusLine = text.substring(0, firstLineEnd).split(" ", 3);
    if (statusLine.length < 2) {
      throw new IOException("invalid HTTP status line: " + text.substring(0, firstLineEnd));
    }
    try {
      return new Response(
          Integer.parseInt(statusLine[1]), text.substring(headersEnd + 4));
    } catch (NumberFormatException exception) {
      throw new IOException("invalid HTTP status line: " + text.substring(0, firstLineEnd), exception);
    }
  }

  private static void requireUrl(String baseUrl) {
    if (baseUrl == null || baseUrl.isBlank()) {
      throw new IllegalArgumentException("base URL must not be blank");
    }
  }

  private static String abbreviate(String value) {
    String singleLine = value.replace('\r', ' ').replace('\n', ' ');
    return singleLine.length() <= 60 ? singleLine : singleLine.substring(0, 60);
  }
}
