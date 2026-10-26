<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use OpenTelemetry\Conformance\Http\ClientWorkload;
use OpenTelemetry\Conformance\Http\Contract;
use OpenTelemetry\Conformance\Http\Response;
use OpenTelemetry\Conformance\Scenario\Environment;
function driveCurlScenario(): void
{
    ClientWorkload::drive(
        Environment::requireValue('MOCK_SERVER_URL'),
        static function (
            string $method,
            string $url,
            ?string $body,
        ): Response {
            $handle = curl_init($url);
            if ($handle === false) {
                throw new \RuntimeException(
                    "could not initialize curl for {$url}",
                );
            }

            $headers = ['User-Agent: ' . Contract::USER_AGENT];
            $options = [
                CURLOPT_CUSTOMREQUEST => $method,
                CURLOPT_HTTPHEADER => $headers,
                CURLOPT_RETURNTRANSFER => true,
            ];
            if ($body !== null) {
                $headers[] = 'Content-Type: ' . Contract::CONTENT_TYPE;
                $options[CURLOPT_HTTPHEADER] = $headers;
                $options[CURLOPT_POSTFIELDS] = $body;
            }
            if (!curl_setopt_array($handle, $options)) {
                throw new \RuntimeException(
                    "could not configure curl for {$url}",
                );
            }

            $responseBody = curl_exec($handle);
            if ($responseBody === false) {
                throw new \RuntimeException(sprintf(
                    'curl request failed: %s',
                    curl_error($handle),
                ));
            }

            return new Response(
                curl_getinfo($handle, CURLINFO_RESPONSE_CODE),
                $responseBody,
            );
        },
    );
}
