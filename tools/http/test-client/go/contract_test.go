// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package httpcontract

import (
	"errors"
	"reflect"
	"strings"
	"testing"
)

const baseURL = "http://127.0.0.1:0"

// driveAgainstTheContract answers with the other side of the same contract,
// which is what a run measures.
func driveAgainstTheContract(t *testing.T) []string {
	t.Helper()
	var sent []string
	err := Drive(baseURL, func(method, url, body string) (Response, error) {
		path := strings.TrimPrefix(url, baseURL)
		sent = append(sent, method+" "+path)
		return Respond(method, path, body), nil
	})
	if err != nil {
		t.Fatalf("driving the contract against itself failed: %v", err)
	}
	return sent
}

func TestBothSidesOfTheContractAgree(t *testing.T) {
	want := []string{
		"GET /users/123",
		"GET /users/123?fields=name&verbose=true",
		"POST /items",
		"GET /status/404",
		"GET /status/500",
	}
	if got := driveAgainstTheContract(t); !reflect.DeepEqual(got, want) {
		t.Errorf("sent %v, want %v", got, want)
	}
}

func TestReadinessIsNotMeasured(t *testing.T) {
	exchanges, err := Exchanges()
	if err != nil {
		t.Fatal(err)
	}
	requests, err := Requests()
	if err != nil {
		t.Fatal(err)
	}
	if len(requests) != len(exchanges)-1 {
		t.Errorf("%d measured requests out of %d exchanges, want one held back for readiness",
			len(requests), len(exchanges))
	}
}

func TestARequestBodyIsEchoedBack(t *testing.T) {
	response := Respond("POST", "/items", `{"name": "widget"}`)

	if response.StatusCode != 201 {
		t.Errorf("POST /items answered %d, want 201", response.StatusCode)
	}
	if !strings.Contains(response.Body, `{"name": "widget"}`) {
		t.Errorf("POST /items answered %q, want the request body echoed back", response.Body)
	}
}

func TestAPathTheContractDoesNotDescribeIsNotFound(t *testing.T) {
	if response := Respond("GET", "/nope", ""); response.StatusCode != 404 {
		t.Errorf("GET /nope answered %d, want 404", response.StatusCode)
	}
}

func TestAQueryStringPicksTheSameAnswer(t *testing.T) {
	plain := Respond("GET", "/users/123", "")
	queried := Respond("GET", "/users/123?fields=name&verbose=true", "")

	if plain != queried {
		t.Errorf("a query string changed the answer: %v then %v", plain, queried)
	}
}

func TestAWrongStatusFailsTheRun(t *testing.T) {
	users, found := Lookup("GET", "/users/123")
	if !found {
		t.Fatal("the contract describes no GET /users/123")
	}

	err := Verify(users, Response{StatusCode: 500, Body: users.ResponseBody})

	if err == nil || !strings.Contains(err.Error(), "answered 500") {
		t.Errorf("verifying a wrong status gave %v, want a failure naming it", err)
	}
}

func TestWhitespaceAndKeyOrderAreTheJSONWritersBusiness(t *testing.T) {
	users, found := Lookup("GET", "/users/123")
	if !found {
		t.Fatal("the contract describes no GET /users/123")
	}

	body := "{ \"name\" :\"Alice\",\n  \"id\": 123 }"
	if err := Verify(users, Response{StatusCode: users.Status, Body: body}); err != nil {
		t.Errorf("verifying differently spelled JSON failed: %v", err)
	}
}

func TestAnAnswerThatIsNotJSONSaysSo(t *testing.T) {
	users, found := Lookup("GET", "/users/123")
	if !found {
		t.Fatal("the contract describes no GET /users/123")
	}

	err := Verify(users, Response{StatusCode: users.Status, Body: "<html>"})

	var contract *Error
	if !errors.As(err, &contract) || !strings.HasPrefix(err.Error(), "not JSON") {
		t.Errorf("verifying a non-JSON answer gave %v, want a contract failure saying so", err)
	}
}

func TestABlankBaseURLIsRefusedBeforeAnythingIsSent(t *testing.T) {
	err := Drive("  ", func(string, string, string) (Response, error) {
		t.Error("a request was sent despite a blank base URL")
		return Response{}, nil
	})

	if err == nil {
		t.Error("a blank base URL was accepted")
	}
}

func TestTheScenarioPortSaysWhoSetsIt(t *testing.T) {
	t.Setenv(PortVariable, "")

	if _, err := ScenarioPort(); err == nil ||
		!strings.Contains(err.Error(), "otel-http-drive") {
		t.Errorf("an unset port gave %v, want a failure naming what sets it", err)
	}
}

func TestTheScenarioPortIsANumber(t *testing.T) {
	t.Setenv(PortVariable, "38217")

	port, err := ScenarioPort()
	if err != nil || port != 38217 {
		t.Errorf("ScenarioPort() = %d, %v, want 38217", port, err)
	}
}
