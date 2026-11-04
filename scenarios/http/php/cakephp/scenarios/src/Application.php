<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

namespace App;

use Cake\Http\BaseApplication;
use Cake\Http\MiddlewareQueue;
use Cake\Routing\Middleware\RoutingMiddleware;
use Cake\Routing\RouteBuilder;

final class Application extends BaseApplication
{
    public function routes(RouteBuilder $routes): void
    {
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
    }

    public function middleware(MiddlewareQueue $middlewareQueue): MiddlewareQueue
    {
        return $middlewareQueue->add(new RoutingMiddleware($this));
    }
}
