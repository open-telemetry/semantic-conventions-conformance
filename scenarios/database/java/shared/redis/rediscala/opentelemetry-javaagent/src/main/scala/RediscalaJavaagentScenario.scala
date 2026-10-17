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
      throw new IllegalArgumentException(
        "expected one Rediscala operation argument"
      )
    }
    val host = ScenarioEnvironment.require("DATABASE_HOST")
    val port = ScenarioEnvironment.require("DATABASE_PORT").toInt
    val database = ScenarioEnvironment.require("DATABASE_NAME").toInt
    require(
      database >= 0,
      "DATABASE_NAME must be a non-negative Redis database index"
    )
    val user = ScenarioEnvironment.require("DATABASE_USER")
    val password = ScenarioEnvironment.requirePresent("DATABASE_PASSWORD")
    implicit val system: ActorSystem = ActorSystem("redis-conformance")
    try {
      val redis = RedisClient(
        host,
        port,
        username = Option.when(password.nonEmpty)(user),
        password = Option.when(password.nonEmpty)(password),
        db = Option.when(database != 0)(database)
      )
      try {
        args(0) match {
          case "set_get" =>
            require(
              Await.result(redis.set("conformance:value", "value"), 5.seconds)
            )
            require(
              Await
                .result(redis.get[String]("conformance:value"), 5.seconds)
                .contains("value")
            )
          case "pipeline" =>
            val first = redis.set("conformance:pipeline:1", "first")
            val second = redis.set("conformance:pipeline:2", "second")
            require(Await.result(first, 5.seconds))
            require(Await.result(second, 5.seconds))
            require(
              Await
                .result(redis.get[String]("conformance:pipeline:1"), 5.seconds)
                .contains("first")
            )
            require(
              Await
                .result(redis.get[String]("conformance:pipeline:2"), 5.seconds)
                .contains("second")
            )
          case "transaction" =>
            val transaction = redis.transaction()
            val first =
              transaction.set("conformance:rediscala:transaction", "value")
            val second =
              transaction.get[String]("conformance:rediscala:transaction")
            Await.result(transaction.exec(), 5.seconds)
            require(Await.result(first, 5.seconds))
            require(Await.result(second, 5.seconds).contains("value"))
          case "error" =>
            val key = "conformance:error"
            require(Await.result(redis.set(key, "not-a-list"), 5.seconds))
            try {
              Await.result(redis.lpush(key, "value"), 5.seconds)
              throw new IllegalStateException(
                "LPUSH unexpectedly accepted a string key"
              )
            } catch {
              case error: Throwable if causedByWrongType(error) =>
            }
          case operation =>
            throw new IllegalArgumentException(
              s"unknown Rediscala operation: $operation"
            )
        }
      } finally {
        redis.stop()
      }
    } finally {
      Await.result(system.terminate(), 5.seconds)
    }
  }

  private def causedByWrongType(error: Throwable): Boolean = {
    Option(error.getMessage).exists(_.contains("WRONGTYPE")) ||
    Option(error.getCause).exists(causedByWrongType)
  }
}
