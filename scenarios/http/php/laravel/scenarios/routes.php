<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Illuminate\Support\Facades\Route;
use OpenTelemetry\Conformance\Http\Contract;
use OpenTelemetry\Conformance\Http\ServerWorkload;

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

Route::get('/health', $answer);
Route::get('/users/{userId}', $answer);
Route::post('/items', $answer);
Route::get('/status/{code}', $answer);
