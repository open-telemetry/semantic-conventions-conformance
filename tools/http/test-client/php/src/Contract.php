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
    public const ACTION_VARIABLE = 'OTEL_CONFORMANCE_SCENARIO_ACTION';
    public const ACTIONS_VARIABLE = 'OTEL_CONFORMANCE_SCENARIO_ACTIONS';

    private const ABBREVIATION_BYTES = 60;

    /** @var list<Exchange>|null */
    private static ?array $exchanges = null;
    private static ?string $actionsRaw = null;

    private function __construct()
    {
    }

    /** @return list<Exchange> */
    public static function exchanges(?string $raw = null): array
    {
        $raw ??= getenv(self::ACTIONS_VARIABLE) ?: null;
        if ($raw === null) {
            throw new ContractException(self::ACTIONS_VARIABLE . ' is not set');
        }
        if (self::$actionsRaw === $raw && self::$exchanges !== null) {
            return self::$exchanges;
        }

        self::$actionsRaw = $raw;
        return self::$exchanges = self::decodeTable($raw);
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

    public static function scenarioRequest(?string $raw = null): Exchange
    {
        $raw ??= getenv(self::ACTION_VARIABLE) ?: null;
        if ($raw === null) {
            throw new ContractException(self::ACTION_VARIABLE . ' is not set');
        }

        return self::decodeAction($raw, self::ACTION_VARIABLE, false);
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
    private static function decodeTable(string $raw): array
    {
        try {
            $document = json_decode($raw, true, 512, JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new ContractException(
                self::ACTIONS_VARIABLE . ' contains malformed JSON',
                0,
                $exception,
            );
        }
        if (!is_array($document) || $document === [] || !array_is_list($document)) {
            throw new ContractException(
                self::ACTIONS_VARIABLE
                . ' must be a non-empty JSON array of actions',
            );
        }

        $exchanges = [];
        foreach ($document as $index => $action) {
            $exchanges[] = self::action(
                $action,
                self::ACTIONS_VARIABLE . "[{$index}]",
                $index === 0,
            );
        }

        return $exchanges;
    }

    private static function decodeAction(
        string $raw,
        string $variable,
        bool $readiness,
    ): Exchange {
        try {
            $action = json_decode($raw, true, 512, JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new ContractException(
                "{$variable} contains malformed JSON",
                0,
                $exception,
            );
        }

        return self::action($action, $variable, $readiness);
    }

    private static function action(
        mixed $action,
        string $where,
        bool $readiness,
    ): Exchange
    {
        if (!is_array($action) || array_is_list($action)) {
            throw new ContractException("{$where} action must be a JSON object");
        }
        self::checkKeys($action, ['request', 'response'], "{$where} action");
        $request = $action['request'] ?? null;
        $response = $action['response'] ?? null;
        if (!is_array($request) || !is_array($response)) {
            throw new ContractException(
                "{$where} action requires request and response objects",
            );
        }
        self::checkKeys($request, ['method', 'path', 'body'], "{$where}.request");
        self::checkKeys($response, ['status', 'body'], "{$where}.response");

        $method = self::stringField($request, 'method', $where);
        $path = self::stringField($request, 'path', $where);
        if ($method === '' || !str_starts_with($path, '/')) {
            throw new ContractException("{$where} has an invalid request");
        }

        return new Exchange(
            $method,
            $path,
            isset($request['body'])
                ? self::stringField($request, 'body', $where)
                : null,
            self::intField($response, 'status', $where),
            self::stringField($response, 'body', $where),
            $readiness,
            $readiness ? 'runner readiness action' : 'runner action',
        );
    }

    /** @param array<mixed> $value @param list<string> $allowed */
    private static function checkKeys(
        array $value,
        array $allowed,
        string $where,
    ): void {
        $unknown = array_diff(array_keys($value), $allowed);
        if ($unknown !== []) {
            sort($unknown);
            throw new ContractException(
                "{$where} has unknown field(s): " . implode(', ', $unknown),
            );
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
