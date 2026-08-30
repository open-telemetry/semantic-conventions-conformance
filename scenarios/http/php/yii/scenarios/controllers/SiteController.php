<?php

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

declare(strict_types=1);

namespace app\controllers;

use OpenTelemetry\Conformance\Http\Contract;
use OpenTelemetry\Conformance\Http\ServerWorkload;
use yii\web\Controller;
use yii\web\Response;

final class SiteController extends Controller
{
    public $enableCsrfValidation = false;

    public function actionHealth(): Response
    {
        return $this->answer();
    }

    public function actionUsers(string $userId): Response
    {
        return $this->answer();
    }

    public function actionItems(): Response
    {
        return $this->answer();
    }

    public function actionStatus(string $code): Response
    {
        return $this->answer();
    }

    private function answer(): Response
    {
        $request = \Yii::$app->request;
        $contractResponse = ServerWorkload::respond(
            $request->method,
            $request->url,
            $request->rawBody,
        );
        $response = \Yii::$app->response;
        $response->format = Response::FORMAT_RAW;
        $response->statusCode = $contractResponse->statusCode;
        $response->headers->set('Content-Type', Contract::CONTENT_TYPE);
        $response->content = $contractResponse->body;

        return $response;
    }
}
