<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

use Config\Services;

$routes = Services::routes();
$routes->setDefaultNamespace('App\Controllers');
$routes->get('health', 'Conformance::health');
$routes->get('users/(:segment)', 'Conformance::users/$1');
$routes->post('items', 'Conformance::items');
$routes->get('status/(:num)', 'Conformance::status/$1');
