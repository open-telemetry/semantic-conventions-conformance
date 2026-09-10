<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

namespace OpenTelemetry\Conformance\Http;

final readonly class Exchange
{
    public function __construct(
        public string $method,
        public string $path,
        public ?string $body,
        public int $status,
        public string $responseBody,
        public bool $readiness,
        public string $description,
    ) {
    }

    public function renderResponseBody(?string $requestBody): string
    {
        return str_replace(
            '${requestBody}',
            $requestBody === null || $requestBody === '' ? '{}' : $requestBody,
            $this->responseBody,
        );
    }
}
