<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

namespace OpenTelemetry\Conformance\Http;

use JsonException;

final class Contract
{
    public const CONTENT_TYPE = 'application/json';
    public const USER_AGENT = 'otel-http-conformance/1';

    private const ABBREVIATION_BYTES = 60;
    private const CHECKOUT_PATH = 'tools/http/test-client/contract.json';

    /** @var list<Exchange>|null */
    private static ?array $exchanges = null;

    private function __construct()
    {
    }

    /** @return list<Exchange> */
    public static function exchanges(): array
    {
        return self::$exchanges ??= self::load();
    }

    /** @return list<Exchange> */
    public static function requests(): array
    {
        return array_values(array_filter(
            self::exchanges(),
            static fn (Exchange $exchange): bool => !$exchange->readiness,
        ));
    }

    public static function exchange(string $method, string $target): ?Exchange
    {
        $path = self::withoutQuery($target);
        foreach (self::exchanges() as $exchange) {
            if (
                $exchange->method === $method
                && self::withoutQuery($exchange->path) === $path
            ) {
                return $exchange;
            }
        }

        return null;
    }

    public static function parse(string $json): mixed
    {
        try {
            return json_decode($json, false, 512, JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new ContractException(
                'not JSON: ' . self::abbreviate($json),
                0,
                $exception,
            );
        }
    }

    public static function abbreviate(string $value): string
    {
        $singleLine = str_replace(["\r", "\n"], ' ', $value);
        $length = strlen($singleLine);

        return $length <= self::ABBREVIATION_BYTES
            ? $singleLine
            : substr($singleLine, 0, self::ABBREVIATION_BYTES)
                . "... ({$length} bytes total)";
    }

    private static function withoutQuery(string $target): string
    {
        $query = strpos($target, '?');

        return $query === false ? $target : substr($target, 0, $query);
    }

    /** @return list<Exchange> */
    private static function load(): array
    {
        $path = self::locate();
        $contents = file_get_contents($path);
        if ($contents === false) {
            throw new ContractException("could not read {$path}");
        }

        try {
            $document = json_decode(
                $contents,
                true,
                512,
                JSON_THROW_ON_ERROR,
            );
        } catch (JsonException $exception) {
            throw new ContractException(
                "could not parse {$path}",
                0,
                $exception,
            );
        }
        if (!is_array($document) || !isset($document['requests'])
            || !is_array($document['requests']) || $document['requests'] === []
        ) {
            throw new ContractException("{$path} describes no requests");
        }

        $exchanges = [];
        foreach ($document['requests'] as $entry) {
            if (!is_array($entry)) {
                throw new ContractException("{$path} has an invalid request");
            }
            $exchanges[] = new Exchange(
                self::stringField($entry, 'method', $path),
                self::stringField($entry, 'path', $path),
                isset($entry['body'])
                    ? self::stringField($entry, 'body', $path)
                    : null,
                self::intField($entry, 'status', $path),
                self::stringField($entry, 'responseBody', $path),
                isset($entry['readiness'])
                    ? self::boolField($entry, 'readiness', $path)
                    : false,
                self::stringField($entry, 'description', $path),
            );
        }

        return $exchanges;
    }

    private static function locate(): string
    {
        $beside = dirname(__DIR__, 2) . DIRECTORY_SEPARATOR . 'contract.json';
        if (is_file($beside)) {
            return $beside;
        }

        $directory = getcwd();
        if ($directory === false) {
            throw new ContractException('could not read the working directory');
        }
        while (true) {
            $candidate = $directory . DIRECTORY_SEPARATOR
                . str_replace('/', DIRECTORY_SEPARATOR, self::CHECKOUT_PATH);
            if (is_file($candidate)) {
                return $candidate;
            }
            $parent = dirname($directory);
            if ($parent === $directory) {
                throw new ContractException(
                    'no ' . self::CHECKOUT_PATH
                    . ' at or above the working directory',
                );
            }
            $directory = $parent;
        }
    }

    /** @param array<mixed> $entry */
    private static function stringField(
        array $entry,
        string $field,
        string $path,
    ): string {
        if (!isset($entry[$field]) || !is_string($entry[$field])) {
            throw new ContractException(
                "{$path} request field {$field} must be a string",
            );
        }

        return $entry[$field];
    }

    /** @param array<mixed> $entry */
    private static function intField(
        array $entry,
        string $field,
        string $path,
    ): int {
        if (!isset($entry[$field]) || !is_int($entry[$field])) {
            throw new ContractException(
                "{$path} request field {$field} must be an integer",
            );
        }

        return $entry[$field];
    }

    /** @param array<mixed> $entry */
    private static function boolField(
        array $entry,
        string $field,
        string $path,
    ): bool {
        if (!isset($entry[$field]) || !is_bool($entry[$field])) {
            throw new ContractException(
                "{$path} request field {$field} must be a boolean",
            );
        }

        return $entry[$field];
    }
}
