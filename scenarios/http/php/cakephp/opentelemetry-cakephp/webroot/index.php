<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use App\Application;
use Cake\Http\Server;
use Cake\Http\ServerRequestFactory;

if (PHP_SAPI === 'cli-server') {
    $_SERVER['PHP_SELF'] = '/index.php';
}

require dirname(__DIR__) . '/config/bootstrap.php';

$server = new Server(new Application(CONFIG));
$server->emit($server->run(ServerRequestFactory::fromGlobals()));
