<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use OpenTelemetry\Conformance\Http\Contract;
use OpenTelemetry\Conformance\Http\ServerWorkload;
use Psr\Http\Message\ResponseInterface;
use Psr\Http\Message\ServerRequestInterface;
use Slim\App;
use Slim\Factory\AppFactory;

function createSlimScenario(): App
{
    $app = AppFactory::create();
    $answer = static function (
        ServerRequestInterface $request,
        ResponseInterface $response,
    ): ResponseInterface {
        $target = $request->getUri()->getPath();
        if ($request->getUri()->getQuery() !== '') {
            $target .= '?' . $request->getUri()->getQuery();
        }
        $contractResponse = ServerWorkload::respond(
            $request->getMethod(),
            $target,
            (string) $request->getBody(),
        );
        $response->getBody()->write($contractResponse->body);

        return $response
            ->withHeader('Content-Type', Contract::CONTENT_TYPE)
            ->withStatus($contractResponse->statusCode);
    };

    $app->get('/health', $answer);
    $app->get('/users/{userId}', $answer);
    $app->post('/items', $answer);
    $app->get('/status/{code}', $answer);

    return $app;
}
