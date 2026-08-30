/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.ktor.application.install
import io.opentelemetry.conformance.http.ktor.v1.Ktor1ServerScenario
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk
import io.opentelemetry.instrumentation.ktor.v1_0.KtorServerTelemetry

object Ktor1LibraryServerScenario {
    @JvmStatic
    fun main(args: Array<String>) {
        ScenarioSdk.initialize().use { sdk ->
            Ktor1ServerScenario.run {
                install(KtorServerTelemetry) {
                    setOpenTelemetry(sdk.openTelemetry())
                }
            }
        }
    }
}
