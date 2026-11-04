<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use OpenTelemetry\Conformance\Http\ClientWorkload;
use OpenTelemetry\Conformance\Http\Contract;
use OpenTelemetry\Conformance\Http\Response;
use OpenTelemetry\Conformance\Scenario\Environment;
use React\Http\Browser;

use function React\Async\await;

function driveReactPhpScenario(): void
{
    $browser = (new Browser())->withRejectErrorResponse(false);
    ClientWorkload::drive(
        Environment::requireValue('MOCK_SERVER_URL'),
        static function (
            string $method,
            string $url,
            ?string $body,
        ) use ($browser): Response {
            $headers = ['User-Agent' => Contract::USER_AGENT];
            if ($body !== null) {
                $headers['Content-Type'] = Contract::CONTENT_TYPE;
            }
            $response = await($browser->request(
                $method,
                $url,
                $headers,
                $body ?? '',
            ));

            return new Response(
                $response->getStatusCode(),
                (string) $response->getBody(),
            );
        },
    );
}
