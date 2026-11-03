<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

return [
    'GET health' => 'site/health',
    'GET users/<userId:\d+>' => 'site/users',
    'POST items' => 'site/items',
    'GET status/<code:\d+>' => 'site/status',
];
