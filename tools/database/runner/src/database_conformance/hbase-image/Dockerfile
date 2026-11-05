# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

ARG HBASE_VERSION=3.0.0
ARG HBASE_SHA512=8290bc3cece084d36f7f47aae726268c7332e4828c6e8599df1343b03348e93f91165fad03ac6107bfbf0d8535e72024fa5d19217890d2848d013d8418a584ed

# The runtime image has no curl, so a separate stage fetches the distribution.
# archive.apache.org throttles and resets CI connections, so the CDN mirrors are
# tried first and the archive (which keeps every release) is the last resort.
# The pinned checksum makes every mirror equally trustworthy.
FROM curlimages/curl:8.17.0@sha256:935d9100e9ba842cdb060de42472c7ca90cfe9a7c96e4dacb55e79e560b3ff40 AS download

ARG HBASE_VERSION
ARG HBASE_SHA512

WORKDIR /tmp
RUN set -eu; \
    path="hbase/${HBASE_VERSION}/hbase-${HBASE_VERSION}-bin.tar.gz"; \
    for url in \
        "https://dlcdn.apache.org/${path}" \
        "https://downloads.apache.org/${path}" \
        "https://archive.apache.org/dist/${path}"; \
    do \
        echo "Downloading ${url}"; \
        if curl --fail --silent --show-error --location \
                --connect-timeout 30 --retry 5 --retry-all-errors --retry-delay 5 \
                --output hbase.tar.gz "${url}" \
            && echo "${HBASE_SHA512}  hbase.tar.gz" | sha512sum -c -s; \
        then \
            exit 0; \
        fi; \
        echo "Could not fetch a verified distribution from ${url}" >&2; \
        rm -f hbase.tar.gz; \
    done; \
    exit 1

FROM eclipse-temurin:25-jre-jammy@sha256:659b528cca74a0edc5c25315ec5819f35bce40bbcec645c4c534987e4c6be7c1

ARG HBASE_VERSION
ARG HBASE_SHA512

COPY --from=download /tmp/hbase.tar.gz /tmp/hbase.tar.gz
RUN echo "${HBASE_SHA512}  /tmp/hbase.tar.gz" | sha512sum --check --strict \
    && mkdir /opt/hbase \
    && tar --extract --gzip --file /tmp/hbase.tar.gz --strip-components 1 --directory /opt/hbase \
    && rm /tmp/hbase.tar.gz

ENV HBASE_HOME=/opt/hbase
ENV PATH="${HBASE_HOME}/bin:${PATH}"

COPY hbase-site.xml ${HBASE_HOME}/conf/hbase-site.xml

EXPOSE 2181 16000 16020

CMD ["bash", "-c", "hbase-daemon.sh start zookeeper && hbase-daemon.sh start master && hbase-daemon.sh start regionserver && exec tail -F ${HBASE_HOME}/logs/*"]
