<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

return [
    'debug' => false,
    'App' => [
        'namespace' => 'App',
        'encoding' => 'UTF-8',
        'defaultLocale' => 'en_US',
        'defaultTimezone' => 'UTC',
        'base' => false,
        'dir' => 'scenarios/src',
        'webroot' => 'webroot',
        'wwwRoot' => WWW_ROOT,
        'baseUrl' => false,
        'fullBaseUrl' => false,
        'imageBaseUrl' => 'img/',
        'cssBaseUrl' => 'css/',
        'jsBaseUrl' => 'js/',
        'paths' => [
            'plugins' => [ROOT . DS . 'plugins' . DS],
            'templates' => [ROOT . DS . 'templates' . DS],
            'locales' => [RESOURCES . 'locales' . DS],
        ],
    ],
    'Error' => [
        'errorLevel' => E_ALL,
        'exceptionRenderer' => 'Cake\Error\ExceptionRenderer',
        'skipLog' => [],
        'log' => true,
        'trace' => true,
        'ignoredDeprecationPaths' => [],
    ],
    'Session' => ['defaults' => 'php'],
    'Cache' => [
        'default' => [
            'className' => 'Cake\Cache\Engine\FileEngine',
            'path' => CACHE,
        ],
        '_cake_core_' => [
            'className' => 'Cake\Cache\Engine\FileEngine',
            'path' => CACHE . 'persistent' . DS,
            'serialize' => true,
        ],
        '_cake_model_' => [
            'className' => 'Cake\Cache\Engine\FileEngine',
            'path' => CACHE . 'models' . DS,
            'serialize' => true,
        ],
        '_cake_routes_' => [
            'className' => 'Cake\Cache\Engine\FileEngine',
            'path' => CACHE . 'persistent' . DS,
            'serialize' => true,
        ],
    ],
    'Log' => [],
    'Security' => [
        'salt' => 'opentelemetry-conformance-cakephp',
    ],
    'Datasources' => [],
];
