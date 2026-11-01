/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.ktor

import io.ktor.http.ContentType
import io.ktor.http.HttpStatusCode
import io.ktor.server.application.Application
import io.ktor.server.application.call
import io.ktor.server.engine.embeddedServer
import io.ktor.server.netty.Netty
import io.ktor.server.request.httpMethod
import io.ktor.server.request.receiveText
import io.ktor.server.request.uri
import io.ktor.server.response.respondText
import io.ktor.server.routing.RoutingContext
import io.ktor.server.routing.get
import io.ktor.server.routing.post
import io.ktor.server.routing.routing
import io.opentelemetry.conformance.http.HttpServerWorkload
import io.opentelemetry.conformance.scenario.ScenarioLifecycle

/** Hosts the shared HTTP exchanges on Ktor 3 until the driver says stop. */
object KtorServerScenario {
    fun run(configureTelemetry: Application.() -> Unit) {
        val server =
            embeddedServer(
                Netty,
                host = "127.0.0.1",
                port = HttpServerWorkload.scenarioPort(),
            ) {
                configureTelemetry()
                routing {
                    get("/health") { answer() }
                    get("/users/{userId}") { answer() }
                    post("/items") { answer(call.receiveText()) }
                    get("/status/{code}") { answer() }
                }
            }

        server.start(wait = false)
        try {
            ScenarioLifecycle.waitForEof()
        } finally {
            server.stop(1_000, 5_000)
        }
    }

    private suspend fun RoutingContext.answer(body: String? = null) {
        val response =
            HttpServerWorkload.respond(
                call.request.httpMethod.value,
                call.request.uri,
                body?.ifEmpty { null },
            )
        call.respondText(
            response.body(),
            ContentType.Application.Json,
            HttpStatusCode.fromValue(response.statusCode()),
        )
    }
}
