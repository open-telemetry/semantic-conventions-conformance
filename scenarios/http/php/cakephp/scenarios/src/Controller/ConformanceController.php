<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

namespace App\Controller;

use Cake\Controller\Controller;
use Cake\Http\Response;
use OpenTelemetry\Conformance\Http\Contract;
use OpenTelemetry\Conformance\Http\ServerWorkload;

final class ConformanceController extends Controller
{
    public function answer(): Response
    {
        $contractResponse = ServerWorkload::respond(
            $this->request->getMethod(),
            $this->request->getRequestTarget(),
            (string) $this->request->getBody(),
        );

        return $this->response
            ->withType(Contract::CONTENT_TYPE)
            ->withStatus($contractResponse->statusCode)
            ->withStringBody($contractResponse->body);
    }
}
