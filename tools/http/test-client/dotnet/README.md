# .NET HTTP test client

The [contract](../contract.json), as .NET reads it — enough for a scenario to
answer a concrete request or to send the measured ones, and nothing more.

`HttpContract` reads the file, `HttpServerWorkload.Respond` looks up the answer
for any .NET framework, and `HttpClientWorkload.DriveAsync` sends the requests
through whatever the scenario hands it. Both halves are exercised against each
other by this project's unit tests, so a change to either is caught here rather
than by a scenario failing to agree with Python.

The build embeds `contract.json` as a manifest resource rather than copying it
into the tree, so the file stays written down once and a scenario reads the same
bytes every other language does.

`HttpClientWorkload.Sender` returns a `Task`, because the .NET HTTP libraries a
scenario measures are asynchronous and forcing a synchronous shape onto them
would measure a blocking call the library was never meant to make.
