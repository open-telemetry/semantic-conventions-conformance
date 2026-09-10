<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

namespace OpenTelemetry\Conformance\Http;

final class ServerWorkload
{
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
}
