<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use GuzzleHttp\Client;
use GuzzleHttp\RequestOptions;
use OpenTelemetry\Conformance\Http\ClientWorkload;
use OpenTelemetry\Conformance\Http\Contract;
use OpenTelemetry\Conformance\Http\Response;
use OpenTelemetry\Conformance\Scenario\Environment;

function driveGuzzleScenario(): void
{
    $client = new Client(['http_errors' => false]);
    ClientWorkload::drive(
        Environment::require('MOCK_SERVER_URL'),
        static function (
            string $method,
            string $url,
            ?string $body,
        ) use ($client): Response {
            $options = [
                RequestOptions::HEADERS => [
                    'User-Agent' => Contract::USER_AGENT,
                ],
            ];
            if ($body !== null) {
                $options[RequestOptions::BODY] = $body;
                $options[RequestOptions::HEADERS]['Content-Type']
                    = Contract::CONTENT_TYPE;
            }
            $response = $client->request($method, $url, $options);

            return new Response(
                $response->getStatusCode(),
                (string) $response->getBody(),
            );
        },
    );
}
