<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use OpenTelemetry\Conformance\Http\ClientWorkload;
use OpenTelemetry\Conformance\Http\Contract;
use OpenTelemetry\Conformance\Http\ContractException;
use OpenTelemetry\Conformance\Http\Response;
use OpenTelemetry\Conformance\Http\ServerWorkload;

require dirname(__DIR__) . '/vendor/autoload.php';

function check(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

$requests = Contract::requests();
check(count($requests) === 5, 'the measured contract has five requests');
check(
    Contract::exchange('GET', '/users/123?fields=name')?->path
        === '/users/123',
    'lookup ignores the query string',
);

$created = ServerWorkload::respond(
    'POST',
    '/items',
    '{"name": "widget"}',
);
check($created->statusCode === 201, 'the server returns the contract status');
check(
    Contract::parse($created->body)
        == Contract::parse(
            '{"created": true, "payload": {"name": "widget"}}',
        ),
    'the server echoes the request body',
);

$sent = [];
ClientWorkload::drive(
    'http://example.test',
    static function (
        string $method,
        string $url,
        ?string $body,
    ) use (&$sent): Response {
        $sent[] = [$method, $url, $body];
        $target = parse_url($url, PHP_URL_PATH);
        $query = parse_url($url, PHP_URL_QUERY);
        check(is_string($target), 'the sender receives a URL path');
        if (is_string($query)) {
            $target .= '?' . $query;
        }

        return ServerWorkload::respond($method, $target, $body);
    },
);
check(count($sent) === 5, 'the client sends every measured request');

try {
    ClientWorkload::verify($requests[0], new Response(500, '{}'));
    throw new RuntimeException('a wrong response should fail');
} catch (ContractException $exception) {
    check(
        str_contains($exception->getMessage(), 'answered 500'),
        'the failure names the wrong status',
    );
}

try {
    ClientWorkload::verify(
        $requests[0],
        new Response(200, '{"id": "123", "name": "Alice"}'),
    );
    throw new RuntimeException('a wrong JSON value type should fail');
} catch (ContractException $exception) {
    check(
        str_contains($exception->getMessage(), '"123"'),
        'the failure keeps the wrong JSON value type',
    );
}

fwrite(STDOUT, "PHP HTTP contract tests passed\n");
