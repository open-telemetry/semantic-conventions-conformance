/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.ktor.KtorClientScenario
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk
import io.opentelemetry.instrumentation.ktor.v3_0.KtorClientTelemetry

object KtorLibraryClientScenario {
    @JvmStatic
    fun main(args: Array<String>) {
        ScenarioSdk.initialize().use { sdk ->
            KtorClientScenario.run {
                install(KtorClientTelemetry) {
                    setOpenTelemetry(sdk.openTelemetry())
                }
            }
        }
    }
}
