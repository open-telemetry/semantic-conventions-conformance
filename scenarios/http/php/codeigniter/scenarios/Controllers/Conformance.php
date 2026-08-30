<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

namespace App\Controllers;

use CodeIgniter\HTTP\ResponseInterface;
use OpenTelemetry\Conformance\Http\Contract;
use OpenTelemetry\Conformance\Http\ServerWorkload;

final class Conformance extends BaseController
{
    public function health(): ResponseInterface
    {
        return $this->answer();
    }

    public function users(string $userId): ResponseInterface
    {
        return $this->answer();
    }

    public function items(): ResponseInterface
    {
        return $this->answer();
    }

    public function status(string $code): ResponseInterface
    {
        return $this->answer();
    }

    private function answer(): ResponseInterface
    {
        $contractResponse = ServerWorkload::respond(
            $this->request->getMethod(),
            $_SERVER['REQUEST_URI'],
            $this->request->getBody(),
        );

        return $this->response
            ->setStatusCode($contractResponse->statusCode)
            ->setHeader('Content-Type', Contract::CONTENT_TYPE)
            ->setBody($contractResponse->body);
    }
}
