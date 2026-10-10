<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use Cake\Core\Configure;

require __DIR__ . '/paths.php';
require ROOT . DS . 'vendor' . DS . 'autoload.php';
require CORE_PATH . 'config' . DS . 'bootstrap.php';

foreach (
    [
        TMP,
        LOGS,
        CACHE,
        CACHE . 'models',
        CACHE . 'persistent',
    ] as $directory
) {
    if (!is_dir($directory) && !mkdir($directory, recursive: true)) {
        throw new RuntimeException("could not create directory: {$directory}");
    }
}

Configure::load('app', 'default', false);
date_default_timezone_set((string) Configure::read('App.defaultTimezone'));
mb_internal_encoding((string) Configure::read('App.encoding'));
