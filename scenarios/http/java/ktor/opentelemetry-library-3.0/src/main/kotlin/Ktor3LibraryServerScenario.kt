/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.ktor.server.application.install
import io.opentelemetry.conformance.http.ktor.v3.Ktor3ServerScenario
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk
import io.opentelemetry.instrumentation.ktor.v3_0.KtorServerTelemetry

object Ktor3LibraryServerScenario {
    @JvmStatic
    fun main(args: Array<String>) {
        ScenarioSdk.initialize().use { sdk ->
            Ktor3ServerScenario.run {
                install(KtorServerTelemetry) {
                    setOpenTelemetry(sdk.openTelemetry())
                }
            }
        }
    }
}
