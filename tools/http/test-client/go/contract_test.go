// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package httpcontract

import (
	"encoding/json"
	"errors"
	"io"
	"os"
	"reflect"
	"strings"
	"testing"
)

const baseURL = "http://127.0.0.1:0"
const testActions = `[
{"request":{"method":"GET","path":"/health"},"response":{"status":200,"body":"{\"ok\": true}"}},
{"request":{"method":"GET","path":"/users/123"},"response":{"status":200,"body":"{\"id\": 123, \"name\": \"Alice\"}"}},
{"request":{"method":"GET","path":"/users/123?fields=name&verbose=true"},"response":{"status":200,"body":"{\"id\": 123, \"name\": \"Alice\"}"}},
{"request":{"method":"POST","path":"/items","body":"{\"name\": \"widget\"}"},"response":{"status":201,"body":"{\"created\": true, \"payload\": ${requestBody}}"}},
{"request":{"method":"GET","path":"/status/404"},"response":{"status":404,"body":"{\"message\": \"status 404\"}"}},
{"request":{"method":"GET","path":"/status/500"},"response":{"status":500,"body":"{\"message\": \"status 500\"}"}}
]`

func TestMain(m *testing.M) {
	if err := os.Setenv(ActionsVariable, testActions); err != nil {
		panic(err)
	}
	if err := os.Setenv(ActionVariable, rawAction(0)); err != nil {
		panic(err)
	}
	os.Exit(m.Run())
}

func rawAction(index int) string {
	var actions []json.RawMessage
	if err := json.Unmarshal([]byte(testActions), &actions); err != nil {
		panic(err)
	}
	return string(actions[index+1])
}

// driveAgainstTheContract answers with the other side of the same contract,
// which is what a run measures.
func driveAgainstTheContract(t *testing.T, output io.Writer) []string {
	t.Helper()
	var sent []string
	requests, err := Requests()
	if err != nil {
		t.Fatal(err)
	}
	for index := range requests {
		t.Setenv(ActionVariable, rawAction(index))
		err := Drive(baseURL, output, func(method, url, body string) (Response, error) {
			path := strings.TrimPrefix(url, baseURL)
			sent = append(sent, method+" "+path)
			return Respond(method, path, body)
		})
		if err != nil {
			t.Fatalf("driving contract entry %d against itself failed: %v", index, err)
		}
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
	if got := driveAgainstTheContract(t, io.Discard); !reflect.DeepEqual(got, want) {
		t.Errorf("sent %v, want %v", got, want)
	}
}

func TestScenarioRequestDecodesEveryMeasuredRequest(t *testing.T) {
	requests, err := Requests()
	if err != nil {
		t.Fatal(err)
	}
	for index, want := range requests {
		t.Setenv(ActionVariable, rawAction(index))
		got, err := ScenarioRequest()
		if err != nil {
			t.Fatal(err)
		}
		if got != want {
			t.Errorf("ScenarioRequest() = %v, want %v", got, want)
		}
	}
}

func TestScenarioRequestRequiresValidJSON(t *testing.T) {
	for _, value := range []string{"", "[]", `{"request":{}}`} {
		t.Run(value, func(t *testing.T) {
			t.Setenv(ActionVariable, value)
			if _, err := ScenarioRequest(); err == nil {
				t.Errorf("ScenarioRequest() accepted %q", value)
			}
		})
	}
}

func TestDriveWritesProgressToItsOutput(t *testing.T) {
	var output strings.Builder

	driveAgainstTheContract(t, &output)

	if !strings.Contains(output.String(), "GET /users/123 -> 200") {
		t.Errorf("Drive() wrote %q, want request progress", output.String())
	}
}

func TestProgressAbbreviationDoesNotSplitUTF8(t *testing.T) {
	prefix := strings.Repeat("x", progressBodyLimit-1)
	got := abbreviate(prefix + "\u00e9\u00e9")
	want := prefix + "\u00e9"
	if got != want {
		t.Errorf("abbreviate() = %q, want %q", got, want)
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

func TestAContractAnswerThatIsNotJSONNamesTheRequest(t *testing.T) {
	exchange := Exchange{
		Method:       "GET",
		Path:         "/malformed",
		Status:       200,
		ResponseBody: "<html>",
	}

	err := Verify(exchange, Response{StatusCode: exchange.Status, Body: "{}"})

	if err == nil || !strings.HasPrefix(err.Error(), "GET /malformed: not JSON") {
		t.Errorf("verifying a non-JSON contract answer gave %v, want a failure naming the request", err)
	}
}

func TestLookupPrefersAnExactQueryString(t *testing.T) {
	path := "/users/123?fields=name&verbose=true"
	exchange, found, err := Lookup("GET", path)
	if err != nil {
		t.Fatal(err)
	}
	if !found {
		t.Fatalf("the contract describes no GET %s", path)
	}
	if exchange.Path != path {
		t.Errorf("GET %s selected %s", path, exchange.Path)
	}
}

func TestLookupFallsBackToThePathForAnUnknownQuery(t *testing.T) {
	exchange, found, err := Lookup("GET", "/users/123?fields=other")
	if err != nil {
		t.Fatal(err)
	}
	if !found {
		t.Fatal("the contract describes no GET /users/123")
	}
	if exchange.Path != "/users/123" {
		t.Errorf("an unknown query selected %s, want /users/123", exchange.Path)
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

	body := "<html>" + strings.Repeat("x", 1000)
	err = Verify(users, Response{StatusCode: users.Status, Body: body})

	var contract *Error
	if !errors.As(err, &contract) ||
		!strings.HasPrefix(err.Error(), "GET /users/123: not JSON") {
		t.Errorf("verifying a non-JSON answer gave %v, want a contract failure naming the request", err)
	}
	var syntax *json.SyntaxError
	if !errors.As(err, &syntax) {
		t.Errorf("verifying a non-JSON answer gave %v, want the JSON syntax error", err)
	}
	if strings.Contains(err.Error(), body) {
		t.Error("the JSON error contains the full response body")
	}
}

func TestRespondReportsAnActionTableFailure(t *testing.T) {
	t.Setenv(ActionsVariable, "not JSON")

	if _, err := Respond("GET", "/users/123", ""); err == nil {
		t.Error("Respond() accepted malformed action data")
	}
}

func TestABlankBaseURLIsRefusedBeforeAnythingIsSent(t *testing.T) {
	t.Setenv(ActionVariable, rawAction(0))
	err := Drive("  ", io.Discard, func(string, string, string) (Response, error) {
		t.Error("a request was sent despite a blank base URL")
		return Response{}, nil
	})

	if err == nil {
		t.Error("a blank base URL was accepted")
	}
}

func TestANilSenderIsRefusedBeforeAnythingIsSent(t *testing.T) {
	t.Setenv(ActionVariable, rawAction(0))
	err := Drive(baseURL, io.Discard, nil)

	if err == nil || !strings.Contains(err.Error(), "sender") {
		t.Errorf("a nil sender gave %v, want a contract error naming the sender", err)
	}
}

func TestATrailingSlashOnTheBaseURLIsNotRepeated(t *testing.T) {
	t.Setenv(ActionVariable, rawAction(0))
	var firstURL string
	err := Drive(baseURL+"/", io.Discard, func(method, url, body string) (Response, error) {
		if firstURL == "" {
			firstURL = url
		}
		return Respond(method, strings.TrimPrefix(url, baseURL), body)
	})

	if err != nil {
		t.Fatal(err)
	}
	if want := baseURL + "/users/123"; firstURL != want {
		t.Errorf("first request URL = %s, want %s", firstURL, want)
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
