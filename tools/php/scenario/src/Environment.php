<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

namespace OpenTelemetry\Conformance\Scenario;

use RuntimeException;

final class Environment
{
    private function __construct()
    {
    }

    public static function require(string $name): string
    {
        $value = getenv($name);
        if ($value === false || $value === '') {
            throw new RuntimeException(
                "required environment variable is missing: {$name}",
            );
        }

        return $value;
    }
}
