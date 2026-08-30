<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use Nyholm\Psr7\Request;
use OpenTelemetry\Conformance\Http\ClientWorkload;
use OpenTelemetry\Conformance\Http\Contract;
use OpenTelemetry\Conformance\Http\Response;
use OpenTelemetry\Conformance\Scenario\Environment;
use Symfony\Component\HttpClient\Psr18Client;

function drivePsr18Scenario(): void
{
    $client = new Psr18Client();
    ClientWorkload::drive(
        Environment::requireValue('MOCK_SERVER_URL'),
        static function (
            string $method,
            string $url,
            ?string $body,
        ) use ($client): Response {
            $headers = ['User-Agent' => Contract::USER_AGENT];
            if ($body !== null) {
                $headers['Content-Type'] = Contract::CONTENT_TYPE;
            }
            $response = $client->sendRequest(
                new Request($method, $url, $headers, $body ?? ''),
            );

            return new Response(
                $response->getStatusCode(),
                (string) $response->getBody(),
            );
        },
    );
}
