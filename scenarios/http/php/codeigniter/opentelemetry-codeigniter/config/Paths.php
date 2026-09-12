<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

namespace Config;

final class Paths
{
    public string $systemDirectory =
        __DIR__ . '/../vendor/codeigniter4/framework/system';
    public string $appDirectory = __DIR__ . '/../app';
    public string $writableDirectory = __DIR__ . '/../writable';
    public string $testsDirectory = __DIR__ . '/../tests';
    public string $viewDirectory = __DIR__ . '/../app/Views';
    public string $envDirectory = __DIR__ . '/..';
}
