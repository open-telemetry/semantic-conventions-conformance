/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.ktor.server.application.install
import io.opentelemetry.conformance.http.ktor.KtorServerScenario
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk
import io.opentelemetry.instrumentation.ktor.v3_0.KtorServerTelemetry

object KtorLibraryServerScenario {
    @JvmStatic
    fun main(args: Array<String>) {
        ScenarioSdk.initialize().use { sdk ->
            KtorServerScenario.run {
                install(KtorServerTelemetry) {
                    setOpenTelemetry(sdk.openTelemetry())
                }
            }
        }
    }
}
