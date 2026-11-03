<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

require __DIR__ . '/vendor/autoload.php';

defined('YII_DEBUG') or define('YII_DEBUG', false);
defined('YII_ENV') or define('YII_ENV', 'prod');

require __DIR__ . '/vendor/yiisoft/yii2/Yii.php';

$config = [
    'id' => 'opentelemetry-conformance',
    'basePath' => __DIR__,
    'controllerMap' => [
        'site' => ['class' => 'app\controllers\SiteController'],
    ],
    'components' => [
        'request' => [
            'cookieValidationKey' => 'opentelemetry-conformance-yii',
            'scriptUrl' => '/index.php',
        ],
        'urlManager' => [
            'enablePrettyUrl' => true,
            'showScriptName' => false,
            'rules' => require __DIR__ . '/../scenarios/routes.php',
        ],
    ],
];

(new yii\web\Application($config))->run();
