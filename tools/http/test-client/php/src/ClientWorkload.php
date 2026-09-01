<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

namespace OpenTelemetry\Conformance\Http;

final class ClientWorkload
{
    private function __construct()
    {
    }

    /**
     * @param callable(string, string, ?string): Response $sender
     */
    public static function drive(string $baseUrl, callable $sender): void
    {
        if (trim($baseUrl) === '') {
            throw new ContractException('base URL must not be blank');
        }

        foreach (Contract::requests() as $exchange) {
            $response = $sender(
                $exchange->method,
                rtrim($baseUrl, '/') . $exchange->path,
                $exchange->body,
            );
            printf(
                "%s %s -> %d %s\n",
                $exchange->method,
                $exchange->path,
                $response->statusCode,
                Contract::abbreviate($response->body),
            );
            self::verify($exchange, $response);
        }
    }

    public static function verify(
        Exchange $exchange,
        Response $response,
    ): void {
        if ($response->statusCode !== $exchange->status) {
            throw new ContractException(sprintf(
                '%s %s answered %d, but the contract answers %d',
                $exchange->method,
                $exchange->path,
                $response->statusCode,
                $exchange->status,
            ));
        }

        $expected = Contract::parse(
            $exchange->renderResponseBody($exchange->body),
        );
        $actual = Contract::parse($response->body);
        if (!self::jsonEquals($actual, $expected)) {
            throw new ContractException(sprintf(
                '%s %s answered %s, but the contract answers %s',
                $exchange->method,
                $exchange->path,
                json_encode($actual, JSON_THROW_ON_ERROR),
                json_encode($expected, JSON_THROW_ON_ERROR),
            ));
        }
    }

    private static function jsonEquals(mixed $actual, mixed $expected): bool
    {
        if (get_debug_type($actual) !== get_debug_type($expected)) {
            return false;
        }
        if ($actual instanceof \stdClass && $expected instanceof \stdClass) {
            $actualFields = get_object_vars($actual);
            $expectedFields = get_object_vars($expected);
            if (count($actualFields) !== count($expectedFields)) {
                return false;
            }
            foreach ($expectedFields as $key => $value) {
                if (
                    !array_key_exists($key, $actualFields)
                    || !self::jsonEquals($actualFields[$key], $value)
                ) {
                    return false;
                }
            }

            return true;
        }
        if (is_array($actual) && is_array($expected)) {
            if (count($actual) !== count($expected)) {
                return false;
            }
            foreach ($expected as $index => $value) {
                if (
                    !array_key_exists($index, $actual)
                    || !self::jsonEquals($actual[$index], $value)
                ) {
                    return false;
                }
            }

            return true;
        }

        return $actual === $expected;
    }
}
