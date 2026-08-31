/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.ktor

import io.ktor.client.HttpClient
import io.ktor.client.HttpClientConfig
import io.ktor.client.engine.cio.CIO
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.request.header
import io.ktor.client.request.request
import io.ktor.client.request.setBody
import io.ktor.client.statement.bodyAsText
import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpMethod
import io.ktor.http.contentType
import io.opentelemetry.conformance.http.HttpClientWorkload
import io.opentelemetry.conformance.http.HttpContract
import io.opentelemetry.conformance.scenario.ScenarioEnvironment
import kotlinx.coroutines.runBlocking

/** Runs the shared request contract through a Ktor 3 CIO client. */
object KtorClientScenario {
    fun run(configureTelemetry: HttpClientConfig<*>.() -> Unit) {
        HttpClient(CIO) {
            install(HttpTimeout) {
                requestTimeoutMillis = HttpClientWorkload.REQUEST_TIMEOUT.toMillis()
            }
            configureTelemetry()
        }.use { client ->
            HttpClientWorkload.drive(ScenarioEnvironment.require("MOCK_SERVER_URL")) {
                method,
                url,
                body,
                ->
                runBlocking {
                    val response =
                        client.request(url) {
                            this.method = HttpMethod.parse(method)
                            header(HttpHeaders.UserAgent, HttpContract.USER_AGENT)
                            if (body != null) {
                                contentType(ContentType.Application.Json)
                                setBody(body)
                            }
                        }
                    HttpContract.Response(response.status.value, response.bodyAsText())
                }
            }
        }
    }
}
