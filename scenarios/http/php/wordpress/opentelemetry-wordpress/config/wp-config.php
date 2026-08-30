<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

define('DB_NAME', 'opentelemetry_conformance');
define('DB_USER', '');
define('DB_PASSWORD', '');
define('DB_HOST', 'localhost');
define('DB_CHARSET', 'utf8');
define('DB_COLLATE', '');
define('DB_DIR', __DIR__ . '/wordpress-database');
define('DB_FILE', 'wordpress.sqlite');

$table_prefix = 'wp_';

define('WP_DEBUG', false);
define('WP_CONTENT_DIR', dirname(__DIR__) . '/wp-content');
define('WP_CONTENT_URL', 'http://localhost/wp-content');
define('WP_HOME', 'http://' . ($_SERVER['HTTP_HOST'] ?? 'localhost'));
define('WP_SITEURL', WP_HOME);
define('DISABLE_WP_CRON', true);

define('AUTH_KEY', 'opentelemetry-conformance-auth-key');
define('SECURE_AUTH_KEY', 'opentelemetry-conformance-secure-auth-key');
define('LOGGED_IN_KEY', 'opentelemetry-conformance-logged-in-key');
define('NONCE_KEY', 'opentelemetry-conformance-nonce-key');
define('AUTH_SALT', 'opentelemetry-conformance-auth-salt');
define('SECURE_AUTH_SALT', 'opentelemetry-conformance-secure-auth-salt');
define('LOGGED_IN_SALT', 'opentelemetry-conformance-logged-in-salt');
define('NONCE_SALT', 'opentelemetry-conformance-nonce-salt');

defined('ABSPATH') or define('ABSPATH', __DIR__ . '/wordpress/');
require_once ABSPATH . 'wp-settings.php';
