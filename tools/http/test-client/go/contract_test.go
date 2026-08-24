// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package httpcontract

import (
	"errors"
	"reflect"
	"strings"
	"sync"
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
		return Respond(method, path, body)
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

// A renamed contract key binds to the zero value rather than failing, so an
// empty description is how that arrives here.
func TestEveryExchangeSaysWhatItIsFor(t *testing.T) {
	exchanges, err := Exchanges()
	if err != nil {
		t.Fatal(err)
	}
	for _, exchange := range exchanges {
		if strings.TrimSpace(exchange.Description) == "" {
			t.Errorf("%s %s has no description", exchange.Method, exchange.Path)
		}
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
	response, err := Respond("POST", "/items", `{"name": "widget"}`)
	if err != nil {
		t.Fatal(err)
	}

	if response.StatusCode != 201 {
		t.Errorf("POST /items answered %d, want 201", response.StatusCode)
	}
	if !strings.Contains(response.Body, `{"name": "widget"}`) {
		t.Errorf("POST /items answered %q, want the request body echoed back", response.Body)
	}
}

func TestAPathTheContractDoesNotDescribeIsNotFound(t *testing.T) {
	response, err := Respond("GET", "/nope", "")
	if err != nil {
		t.Fatal(err)
	}
	if response.StatusCode != 404 {
		t.Errorf("GET /nope answered %d, want 404", response.StatusCode)
	}
}

func TestAQueryStringPicksTheSameAnswer(t *testing.T) {
	plain, err := Respond("GET", "/users/123", "")
	if err != nil {
		t.Fatal(err)
	}
	queried, err := Respond("GET", "/users/123?fields=name&verbose=true", "")
	if err != nil {
		t.Fatal(err)
	}

	if plain != queried {
		t.Errorf("a query string changed the answer: %v then %v", plain, queried)
	}
}

func TestAWrongStatusFailsTheRun(t *testing.T) {
	users, found, err := Lookup("GET", "/users/123")
	if err != nil {
		t.Fatal(err)
	}
	if !found {
		t.Fatal("the contract describes no GET /users/123")
	}

	err = Verify(users, Response{StatusCode: 500, Body: users.ResponseBody})

	if err == nil || !strings.Contains(err.Error(), "answered 500") {
		t.Errorf("verifying a wrong status gave %v, want a failure naming it", err)
	}
}

func TestWhitespaceAndKeyOrderAreTheJSONWritersBusiness(t *testing.T) {
	users, found, err := Lookup("GET", "/users/123")
	if err != nil {
		t.Fatal(err)
	}
	if !found {
		t.Fatal("the contract describes no GET /users/123")
	}

	body := "{ \"name\" :\"Alice\",\n  \"id\": 123 }"
	if err := Verify(users, Response{StatusCode: users.Status, Body: body}); err != nil {
		t.Errorf("verifying differently spelled JSON failed: %v", err)
	}
}

func TestAnAnswerThatIsNotJSONSaysSo(t *testing.T) {
	users, found, err := Lookup("GET", "/users/123")
	if err != nil {
		t.Fatal(err)
	}
	if !found {
		t.Fatal("the contract describes no GET /users/123")
	}

	err = Verify(users, Response{StatusCode: users.Status, Body: "<html>"})

	var contract *Error
	if !errors.As(err, &contract) || !strings.HasPrefix(err.Error(), "not JSON") {
		t.Errorf("verifying a non-JSON answer gave %v, want a contract failure saying so", err)
	}
}

func TestRespondReportsAContractLoadFailure(t *testing.T) {
	previous := loaded
	t.Cleanup(func() { loaded = previous })
	want := errors.New("contract load failed")
	loaded = sync.OnceValues(func() ([]Exchange, error) {
		return nil, want
	})

	if _, err := Respond("GET", "/users/123", ""); !errors.Is(err, want) {
		t.Errorf("Respond() returned %v, want %v", err, want)
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

func TestTheScenarioPortIsInTheTCPPortRange(t *testing.T) {
	for _, value := range []string{"-1", "0", "65536"} {
		t.Run(value, func(t *testing.T) {
			t.Setenv(PortVariable, value)

			if _, err := ScenarioPort(); err == nil ||
				!strings.Contains(err.Error(), "between 1 and 65535") {
				t.Errorf("ScenarioPort() accepted %s or returned unclear error %v", value, err)
			}
		})
	}
}
