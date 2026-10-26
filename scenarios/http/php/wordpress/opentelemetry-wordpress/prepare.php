<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

function findSqliteDropIn(string $root): string
{
    $entries = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator(
            $root,
            FilesystemIterator::SKIP_DOTS,
        ),
    );
    foreach ($entries as $entry) {
        if (
            $entry->isFile()
            && $entry->getFilename() === 'db.php'
            && str_contains($entry->getPathname(), 'wp-sqlite-db')
        ) {
            return $entry->getPathname();
        }
    }

    throw new RuntimeException('could not find the WordPress SQLite drop-in');
}

$content = __DIR__ . '/wp-content';
$plugins = $content . '/mu-plugins';
foreach ([$content, $plugins, __DIR__ . '/vendor/wordpress-database'] as $path) {
    if (!is_dir($path) && !mkdir($path, recursive: true)) {
        throw new RuntimeException("could not create directory: {$path}");
    }
}

$files = [
    findSqliteDropIn(__DIR__) => $content . '/db.php',
    __DIR__ . '/config/wp-config.php' => __DIR__ . '/vendor/wp-config.php',
    __DIR__ . '/../scenarios/mu-plugins/conformance.php'
        => $plugins . '/conformance.php',
];
foreach ($files as $source => $destination) {
    if (!copy($source, $destination)) {
        throw new RuntimeException("could not copy file: {$destination}");
    }
}

$database = __DIR__ . '/vendor/wordpress-database/wordpress.sqlite';
if (is_file($database)) {
    return;
}

$_SERVER['HTTP_HOST'] = 'localhost';
$_SERVER['REQUEST_METHOD'] = 'GET';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SERVER_PROTOCOL'] = 'HTTP/1.1';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['PHP_SELF'] = '/index.php';

define('WP_INSTALLING', true);
require __DIR__ . '/vendor/wordpress/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/upgrade.php';
wp_install(
    'OpenTelemetry Conformance',
    'conformance',
    'conformance@example.invalid',
    false,
    '',
    'opentelemetry-conformance',
);
