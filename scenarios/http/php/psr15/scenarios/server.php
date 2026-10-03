<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use Nyholm\Psr7\Response as Psr7Response;
use OpenTelemetry\Conformance\Http\Contract;
use OpenTelemetry\Conformance\Http\ServerWorkload;
use Psr\Http\Message\ResponseInterface;
use Psr\Http\Message\ServerRequestInterface;
use Psr\Http\Server\RequestHandlerInterface;

final class ContractRequestHandler implements RequestHandlerInterface
{
    public function handle(ServerRequestInterface $request): ResponseInterface
    {
        $contractResponse = ServerWorkload::respond(
            $request->getMethod(),
            $request->getRequestTarget(),
            (string) $request->getBody(),
        );

        return new Psr7Response(
            $contractResponse->statusCode,
            ['Content-Type' => Contract::CONTENT_TYPE],
            $contractResponse->body,
        );
    }
}
