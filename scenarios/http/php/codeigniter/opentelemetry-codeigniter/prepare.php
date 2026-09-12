<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

function copyCodeIgniterTree(string $source, string $destination): void
{
    if (!is_dir($destination) && !mkdir($destination, recursive: true)) {
        throw new RuntimeException("could not create directory: {$destination}");
    }

    $entries = new DirectoryIterator($source);
    foreach ($entries as $entry) {
        if ($entry->isDot()) {
            continue;
        }
        $target = $destination . DIRECTORY_SEPARATOR . $entry->getFilename();
        if ($entry->isDir()) {
            copyCodeIgniterTree($entry->getPathname(), $target);
        } elseif (!copy($entry->getPathname(), $target)) {
            throw new RuntimeException("could not copy file: {$target}");
        }
    }
}

$application = __DIR__ . '/app';
copyCodeIgniterTree(
    __DIR__ . '/vendor/codeigniter4/framework/app',
    $application,
);
copyCodeIgniterTree(__DIR__ . '/../scenarios', $application);

$writable = __DIR__ . '/writable';
foreach (['cache', 'debugbar', 'logs', 'session', 'uploads'] as $directory) {
    $path = $writable . DIRECTORY_SEPARATOR . $directory;
    if (!is_dir($path) && !mkdir($path, recursive: true)) {
        throw new RuntimeException("could not create directory: {$path}");
    }
}
