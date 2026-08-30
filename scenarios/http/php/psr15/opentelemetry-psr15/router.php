<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use Nyholm\Psr7\Factory\Psr17Factory;
use Nyholm\Psr7Server\ServerRequestCreator;

require __DIR__ . '/vendor/autoload.php';
require __DIR__ . '/../scenarios/server.php';

$factory = new Psr17Factory();
$request = (new ServerRequestCreator(
    $factory,
    $factory,
    $factory,
    $factory,
))->fromGlobals();
$response = (new ContractRequestHandler())->handle($request);

http_response_code($response->getStatusCode());
foreach ($response->getHeaders() as $name => $values) {
    foreach ($values as $value) {
        header("{$name}: {$value}", false);
    }
}
echo $response->getBody();
