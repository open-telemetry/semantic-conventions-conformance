<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use OpenTelemetry\Conformance\Scenario\Environment;
use OpenTelemetry\Conformance\Scenario\Lifecycle;

require dirname(__DIR__) . '/vendor/autoload.php';

putenv('OTEL_CONFORMANCE_PHP_TEST=value');
if (Environment::requireValue('OTEL_CONFORMANCE_PHP_TEST') !== 'value') {
    throw new RuntimeException('the required environment value was not read');
}
putenv('OTEL_CONFORMANCE_PHP_TEST');

$input = fopen('php://memory', 'r+');
if ($input === false) {
    throw new RuntimeException('could not open the test stream');
}
fwrite($input, 'ignored');
rewind($input);
Lifecycle::waitForEof($input);
fclose($input);

fwrite(STDOUT, "PHP scenario support tests passed\n");
