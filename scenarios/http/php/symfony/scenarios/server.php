<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use OpenTelemetry\Conformance\Http\Contract;
use OpenTelemetry\Conformance\Http\ServerWorkload;
use Symfony\Component\EventDispatcher\EventDispatcher;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\RequestStack;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\HttpKernel\Controller\ArgumentResolver;
use Symfony\Component\HttpKernel\Controller\ControllerResolver;
use Symfony\Component\HttpKernel\EventListener\RouterListener;
use Symfony\Component\HttpKernel\HttpKernel;
use Symfony\Component\Routing\Matcher\UrlMatcher;
use Symfony\Component\Routing\RequestContext;
use Symfony\Component\Routing\Route;
use Symfony\Component\Routing\RouteCollection;

function createSymfonyScenario(): HttpKernel
{
    $answer = static function (Request $request): Response {
        $contractResponse = ServerWorkload::respond(
            $request->getMethod(),
            $request->getRequestUri(),
            $request->getContent(),
        );

        return new Response(
            $contractResponse->body,
            $contractResponse->statusCode,
            ['Content-Type' => Contract::CONTENT_TYPE],
        );
    };

    $routes = new RouteCollection();
    $routes->add(
        '/health',
        new Route('/health', ['_controller' => $answer], methods: ['GET']),
    );
    $routes->add(
        '/users/{userId}',
        new Route(
            '/users/{userId}',
            ['_controller' => $answer],
            methods: ['GET'],
        ),
    );
    $routes->add(
        '/items',
        new Route('/items', ['_controller' => $answer], methods: ['POST']),
    );
    $routes->add(
        '/status/{code}',
        new Route(
            '/status/{code}',
            ['_controller' => $answer],
            methods: ['GET'],
        ),
    );

    $requestStack = new RequestStack();
    $dispatcher = new EventDispatcher();
    $dispatcher->addSubscriber(new RouterListener(
        new UrlMatcher($routes, new RequestContext()),
        $requestStack,
    ));

    return new HttpKernel(
        $dispatcher,
        new ControllerResolver(),
        $requestStack,
        new ArgumentResolver(),
    );
}
