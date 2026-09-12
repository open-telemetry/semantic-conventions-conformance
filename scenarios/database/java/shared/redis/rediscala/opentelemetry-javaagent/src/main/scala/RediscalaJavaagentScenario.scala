/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.scenario.ScenarioEnvironment
import org.apache.pekko.actor.ActorSystem
import redis.RedisClient

import scala.concurrent.Await
import scala.concurrent.ExecutionContext.Implicits.global
import scala.concurrent.duration._

object RediscalaJavaagentScenario {
  def main(args: Array[String]): Unit = {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one Rediscala operation argument")
    }
    implicit val system: ActorSystem = ActorSystem("redis-conformance")
    val redis = RedisClient(
      ScenarioEnvironment.require("DATABASE_HOST"),
      ScenarioEnvironment.require("DATABASE_PORT").toInt,
    )
    try {
      args(0) match {
        case "set_get" =>
          require(Await.result(redis.set("conformance:rediscala:value", "value"), 5.seconds))
          require(
            Await.result(redis.get[String]("conformance:rediscala:value"), 5.seconds)
              .contains("value"),
          )
        case "transaction" =>
          val transaction = redis.transaction()
          val first = transaction.set("conformance:rediscala:transaction", "value")
          val second = transaction.get[String]("conformance:rediscala:transaction")
          Await.result(transaction.exec(), 5.seconds)
          require(Await.result(first, 5.seconds))
          require(Await.result(second, 5.seconds).contains("value"))
        case "error" =>
          val key = "conformance:rediscala:error"
          require(Await.result(redis.set(key, "not-a-list"), 5.seconds))
          try {
            Await.result(redis.lpush(key, "value"), 5.seconds)
            throw new IllegalStateException("LPUSH unexpectedly accepted a string key")
          } catch {
            case error: Throwable if causedByWrongType(error) =>
          }
        case operation =>
          throw new IllegalArgumentException(s"unknown Rediscala operation: $operation")
      }
    } finally {
      redis.stop()
      Await.result(system.terminate(), 5.seconds)
    }
  }

  private def causedByWrongType(error: Throwable): Boolean = {
    Option(error.getMessage).exists(_.contains("WRONGTYPE")) ||
    Option(error.getCause).exists(causedByWrongType)
  }
}
