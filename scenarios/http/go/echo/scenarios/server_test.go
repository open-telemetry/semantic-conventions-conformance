// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package scenarios

import (
	"reflect"
	"testing"

	"github.com/labstack/echo/v5"

	"github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/internal/httpservertest"
)

func TestHandlerAnswersContract(t *testing.T) {
	httpservertest.AssertContract(t, newHandler(nil))
}

func TestHandlerUsesMiddleware(t *testing.T) {
	routes := make(map[string]int)
	middleware := func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(context *echo.Context) error {
			routes[context.Request().Method+" "+context.Path()]++
			return next(context)
		}
	}

	httpservertest.AssertContract(t, newHandler(middleware))

	want := map[string]int{
		"GET /health":        1,
		"GET /users/:userId": 2,
		"POST /items":        1,
		"GET /status/:code":  2,
	}
	if !reflect.DeepEqual(routes, want) {
		t.Errorf("middleware routes = %v, want %v", routes, want)
	}
}
