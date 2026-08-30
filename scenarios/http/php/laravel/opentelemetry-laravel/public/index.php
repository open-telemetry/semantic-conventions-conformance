<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use Illuminate\Http\Request;

require dirname(__DIR__) . '/vendor/autoload.php';

$application = require dirname(__DIR__) . '/bootstrap/app.php';
$application->handleRequest(Request::capture());
