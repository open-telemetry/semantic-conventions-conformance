/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.ktor.v3.Ktor3ClientScenario
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk
import io.opentelemetry.instrumentation.ktor.v3_0.KtorClientTelemetry

object Ktor3LibraryClientScenario {
    @JvmStatic
    fun main(args: Array<String>) {
        ScenarioSdk.initialize().use { sdk ->
            Ktor3ClientScenario.run {
                install(KtorClientTelemetry) {
                    setOpenTelemetry(sdk.openTelemetry())
                }
            }
        }
    }
}
