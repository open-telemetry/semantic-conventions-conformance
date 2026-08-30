/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.ktor.server.application.install
import io.opentelemetry.conformance.http.ktor.v2.Ktor2ServerScenario
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk
import io.opentelemetry.instrumentation.ktor.v2_0.KtorServerTelemetry

object Ktor2LibraryServerScenario {
    @JvmStatic
    fun main(args: Array<String>) {
        ScenarioSdk.initialize().use { sdk ->
            Ktor2ServerScenario.run {
                install(KtorServerTelemetry) {
                    setOpenTelemetry(sdk.openTelemetry())
                }
            }
        }
    }
}
