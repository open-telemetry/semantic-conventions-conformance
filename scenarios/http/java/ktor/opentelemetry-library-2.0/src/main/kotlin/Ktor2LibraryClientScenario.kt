/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.ktor.v2.Ktor2ClientScenario
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk
import io.opentelemetry.instrumentation.ktor.v2_0.KtorClientTelemetry

object Ktor2LibraryClientScenario {
    @JvmStatic
    fun main(args: Array<String>) {
        ScenarioSdk.initialize().use { sdk ->
            Ktor2ClientScenario.run {
                install(KtorClientTelemetry) {
                    setOpenTelemetry(sdk.openTelemetry())
                }
            }
        }
    }
}
