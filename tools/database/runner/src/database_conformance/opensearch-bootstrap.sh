# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

set -eu

base_url=http://127.0.0.1:9200

curl --fail --silent --show-error \
  --request PUT \
  --header 'Content-Type: application/json' \
  --data-binary '{
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 0
    },
    "mappings": {
      "properties": {
        "name": {"type": "keyword"},
        "description": {"type": "text"}
      }
    }
  }' \
  "$base_url/conformance"

printf '%s\n' \
  '{"index":{"_id":"1"}}' \
  '{"name":"alpha","description":"first conformance document"}' \
  '{"index":{"_id":"2"}}' \
  '{"name":"bravo","description":"second conformance document"}' |
  curl --fail --silent --show-error \
    --request POST \
    --header 'Content-Type: application/x-ndjson' \
    --data-binary @- \
    "$base_url/conformance/_bulk?refresh=wait_for"
