<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

namespace OpenTelemetry\Conformance\Scenario;

use RuntimeException;

final class Lifecycle
{
    private function __construct()
    {
    }

    /** @param resource|null $input */
    public static function waitForEof($input = null): void
    {
        $stream = $input ?? STDIN;
        while (!feof($stream)) {
            if (fread($stream, 8192) === false) {
                throw new RuntimeException('could not read standard input');
            }
        }
    }
}
