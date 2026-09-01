<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use OpenTelemetry\Conformance\Scenario\Environment;

require dirname(__DIR__) . '/vendor/autoload.php';

putenv('OTEL_CONFORMANCE_PHP_TEST=value');
if (Environment::requireValue('OTEL_CONFORMANCE_PHP_TEST') !== 'value') {
    throw new RuntimeException('the required environment value was not read');
}
putenv('OTEL_CONFORMANCE_PHP_TEST');

fwrite(STDOUT, "PHP scenario support tests passed\n");
