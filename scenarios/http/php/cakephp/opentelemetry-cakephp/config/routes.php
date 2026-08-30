<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use Cake\Routing\RouteBuilder;

return static function (RouteBuilder $routes): void {
    $routes->scope('/', function (RouteBuilder $builder): void {
        $target = [
            'controller' => 'Conformance',
            'action' => 'answer',
        ];
        $builder->get('/health', $target);
        $builder->get('/users/{userId}', $target);
        $builder->post('/items', $target);
        $builder->get('/status/{code}', $target);
    });
};
