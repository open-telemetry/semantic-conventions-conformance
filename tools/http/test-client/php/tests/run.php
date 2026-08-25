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

$workingDirectory = getcwd();
check($workingDirectory !== false, 'the working directory is available');
check(chdir(sys_get_temp_dir()), 'the test can leave the checkout');
try {
    $requests = Contract::requests();
} finally {
    check(chdir($workingDirectory), 'the test restores the working directory');
}
check(count($requests) === 5, 'the measured contract has five requests');
check(
    Contract::exchange('GET', '/users/123?fields=name')?->path
        === '/users/123',
    'lookup ignores the query string',
);

putenv(ServerWorkload::PORT_VARIABLE . '=4317');
check(
    ServerWorkload::scenarioPort() === 4317,
    'the server accepts a valid port',
);
foreach (['-1', '0', '65536', 'not-a-port'] as $invalidPort) {
    putenv(ServerWorkload::PORT_VARIABLE . "={$invalidPort}");
    try {
        ServerWorkload::scenarioPort();
        throw new RuntimeException('an invalid port should fail');
    } catch (ContractException $exception) {
        check(
            str_contains($exception->getMessage(), '1 to 65535'),
            'the port failure names the accepted range',
        );
    }
}
putenv(ServerWorkload::PORT_VARIABLE);

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

$invalidJson = str_repeat('x', 80);
try {
    Contract::parse($invalidJson);
    throw new RuntimeException('invalid JSON should fail');
} catch (ContractException $exception) {
    check(
        $exception->getMessage()
            === 'not JSON: ' . str_repeat('x', 60) . '... (80 bytes total)',
        'invalid JSON is abbreviated in the failure',
    );
    check(
        $exception->getPrevious() instanceof JsonException,
        'the JSON parser failure is preserved',
    );
}

fwrite(STDOUT, "PHP HTTP contract tests passed\n");
