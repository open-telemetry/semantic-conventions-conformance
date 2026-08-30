<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use OpenTelemetry\Conformance\Http\ClientWorkload;
use OpenTelemetry\Conformance\Http\Contract;
use OpenTelemetry\Conformance\Http\Response;
use OpenTelemetry\Conformance\Scenario\Environment;
use Symfony\Component\HttpClient\HttpClient;

function driveSymfonyHttpClientScenario(): void
{
    $client = HttpClient::create();
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
            $response = $client->request($method, $url, [
                'headers' => $headers,
                'body' => $body ?? '',
            ]);

            return new Response(
                $response->getStatusCode(),
                $response->getContent(false),
            );
        },
    );
}
