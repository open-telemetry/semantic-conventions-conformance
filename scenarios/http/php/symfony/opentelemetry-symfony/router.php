<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use Symfony\Component\HttpFoundation\Request;

require __DIR__ . '/vendor/autoload.php';
require __DIR__ . '/../scenarios/server.php';

$kernel = createSymfonyScenario();
$request = Request::createFromGlobals();
$response = $kernel->handle($request);
$response->send();
$kernel->terminate($request, $response);
