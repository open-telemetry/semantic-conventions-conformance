<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

namespace OpenTelemetry\Conformance\Http;

final readonly class Response
{
    public function __construct(
        public int $statusCode,
        public string $body,
    ) {
    }
}
