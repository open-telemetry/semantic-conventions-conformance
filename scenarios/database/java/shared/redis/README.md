# Redis workload

Every Redis client runs the same workload with the same keys, values, and
plain-string encoding in logical database zero:

| Scenario   | Workload                                                                                                           |
| ---------- | ------------------------------------------------------------------------------------------------------------------ |
| `set_get`  | Set `conformance:value` to `value`, then get and verify it.                                                        |
| `pipeline` | Queue `SET conformance:pipeline:1 first` and `SET conformance:pipeline:2 second`, then get and verify both values. |
| `error`    | Set `conformance:error` to `not-a-list`, then run `LPUSH conformance:error value` and verify `WRONGTYPE`.          |

The named scenario contracts live in
[`scenarios/database/contracts`](../../../contracts). They include telemetry
from connection-startup commands. Unlike the SQL workloads, Redis launchers
select a named workload rather than consume an `action` object.

## Connection settings

Launchers use `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`,
`DATABASE_USER`, and `DATABASE_PASSWORD`. Here `DATABASE_NAME` is the Redis
logical database index; an empty password disables authentication. The runner
provides database zero and the `default` user without authentication.

Jedis disables protocol negotiation and `CLIENT SETINFO`, so its workload
telemetry excludes connection-startup commands.

## Telemetry differences

Lettuce's explicit pipelining and Rediscala's implicit pipelining emit one span
per queued command; Jedis and Redisson expose a pipeline batch span. Rediscala
also has a separate `transaction` scenario that records a `MULTI` batch.

Expectations record client differences: Rediscala does not emit query text,
while Jedis does not currently mark the rejected command as an error. Lettuce
records the Redis server's `WRONGTYPE` code in `error.type` rather than the Java
exception class. The contracts do not assert `db.response.status_code` on
rejected `LPUSH` spans while
[#384](https://github.com/open-telemetry/semantic-conventions-conformance/issues/384)
tracks recording conditional semantic-convention violations as findings.

Connection tests require Docker and prepared scenario runtimes. Clients whose
runtimes have not been prepared are skipped locally. Linux CI prepares the
runtimes and requires all 15 database-selection and authentication cases to run
without skips.
