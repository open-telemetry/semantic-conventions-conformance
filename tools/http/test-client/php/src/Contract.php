<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

namespace OpenTelemetry\Conformance\Http;

use JsonException;
use Symfony\Component\Yaml\Exception\ParseException;
use Symfony\Component\Yaml\Yaml;

final class Contract
{
    public const CONTENT_TYPE = 'application/json';
    public const USER_AGENT = 'otel-http-conformance/1';

    private const ABBREVIATION_BYTES = 60;
    private const CHECKOUT_PATH = 'tools/http/test-client/contract.yaml';
    private const SCENARIO_INDEX_VARIABLE =
        'OTEL_CONFORMANCE_SCENARIO_INDEX';

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

    public static function scenarioRequest(?string $index = null): Exchange
    {
        $raw = $index ?? getenv(self::SCENARIO_INDEX_VARIABLE);
        if ($raw === false) {
            throw new ContractException(
                self::SCENARIO_INDEX_VARIABLE . ' is not set',
            );
        }
        if (!preg_match('/^(0|[1-9][0-9]*)$/D', $raw)) {
            throw new ContractException(
                self::SCENARIO_INDEX_VARIABLE
                . ' must be a zero-based decimal index, got '
                . json_encode($raw, JSON_THROW_ON_ERROR),
            );
        }

        $requests = self::requests();
        $selected = (int) $raw;
        if (!isset($requests[$selected])) {
            throw new ContractException(
                self::SCENARIO_INDEX_VARIABLE . "={$raw} selects no contract "
                . 'entry; expected 0..' . (count($requests) - 1),
            );
        }

        return $requests[$selected];
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
            $document = Yaml::parse($contents);
        } catch (ParseException $exception) {
            throw new ContractException(
                "could not parse {$path}",
                0,
                $exception,
            );
        }
        if (!is_array($document) || !isset($document['readiness'])
            || !is_array($document['readiness'])
            || !isset($document['scenarios'])
            || !is_array($document['scenarios'])
            || $document['scenarios'] === []
        ) {
            throw new ContractException("{$path} describes no requests");
        }

        $exchanges = [];
        foreach ([
            [$document['readiness'], true],
            ...array_map(
                static fn (mixed $entry): array => [$entry, false],
                $document['scenarios'],
            ),
        ] as [$entry, $readiness]) {
            if (!is_array($entry)) {
                throw new ContractException("{$path} has an invalid request");
            }
            $action = $entry['action'] ?? null;
            $request = is_array($action) ? ($action['request'] ?? null) : null;
            $response = is_array($action)
                ? ($action['response'] ?? null)
                : null;
            if (!is_array($request) || !is_array($response)) {
                throw new ContractException("{$path} has an invalid request");
            }
            $exchanges[] = new Exchange(
                self::stringField($request, 'method', $path),
                self::stringField($request, 'path', $path),
                isset($request['body'])
                    ? self::stringField($request, 'body', $path)
                    : null,
                self::intField($response, 'status', $path),
                self::stringField($response, 'body', $path),
                $readiness,
                self::stringField($entry, 'description', $path),
            );
        }

        return $exchanges;
    }

    private static function locate(): string
    {
        $beside = dirname(__DIR__, 2) . DIRECTORY_SEPARATOR . 'contract.yaml';
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

}
