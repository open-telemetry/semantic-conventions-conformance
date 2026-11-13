/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.ktor.KtorServerScenario
import io.opentelemetry.conformance.scenario.ScenarioGate

object KtorObiServerScenario {
    @JvmStatic
    fun main(args: Array<String>) {
        ScenarioGate.waitAtGate()
        KtorServerScenario.run {}
    }
}
