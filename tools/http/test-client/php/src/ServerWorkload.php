<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

namespace OpenTelemetry\Conformance\Http;

final class ServerWorkload
{
    public const PORT_VARIABLE = 'OTEL_HTTP_SCENARIO_PORT';

    private function __construct()
    {
    }

    public static function respond(
        string $method,
        string $target,
        ?string $requestBody,
    ): Response {
        $exchange = Contract::exchange($method, $target);
        if ($exchange === null) {
            return new Response(404, '{"message": "no such route"}');
        }

        return new Response(
            $exchange->status,
            $exchange->renderResponseBody($requestBody),
        );
    }

    public static function scenarioPort(): int
    {
        $value = getenv(self::PORT_VARIABLE);
        if ($value === false || $value === '') {
            throw new ContractException(
                self::PORT_VARIABLE
                . ' is not set; a server scenario is started by '
                . '`otel-http-drive`, which chooses the port',
            );
        }
        $port = filter_var(
            $value,
            FILTER_VALIDATE_INT,
            ['options' => ['min_range' => 1, 'max_range' => 65535]],
        );
        if ($port === false) {
            throw new ContractException(
                self::PORT_VARIABLE
                . " must be an integer from 1 to 65535: {$value}",
            );
        }

        return $port;
    }
}
