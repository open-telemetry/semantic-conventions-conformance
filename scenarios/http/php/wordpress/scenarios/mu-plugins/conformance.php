<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use OpenTelemetry\Conformance\Http\Contract;
use OpenTelemetry\Conformance\Http\ServerWorkload;

add_action('template_redirect', static function (): void {
    $requestBody = file_get_contents('php://input');
    $response = ServerWorkload::respond(
        $_SERVER['REQUEST_METHOD'],
        $_SERVER['REQUEST_URI'],
        $requestBody === false ? null : $requestBody,
    );

    global $wp_query;
    $wp_query->is_404 = $response->statusCode === 404;
    status_header($response->statusCode);
    header('Content-Type: ' . Contract::CONTENT_TYPE);
    echo $response->body;
    exit;
}, PHP_INT_MIN);
