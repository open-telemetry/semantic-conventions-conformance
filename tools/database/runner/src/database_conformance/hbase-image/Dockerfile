# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM eclipse-temurin:17-jre-jammy@sha256:c35794d1348777e6bc310b9b7f420098ef8f37e988199549b545fded79a895a2

ARG HBASE_VERSION=3.0.0
ARG HBASE_SHA512=8290bc3cece084d36f7f47aae726268c7332e4828c6e8599df1343b03348e93f91165fad03ac6107bfbf0d8535e72024fa5d19217890d2848d013d8418a584ed

ADD https://archive.apache.org/dist/hbase/${HBASE_VERSION}/hbase-${HBASE_VERSION}-bin.tar.gz /tmp/hbase.tar.gz
RUN echo "${HBASE_SHA512}  /tmp/hbase.tar.gz" | sha512sum --check --strict \
    && mkdir /opt/hbase \
    && tar --extract --gzip --file /tmp/hbase.tar.gz --strip-components 1 --directory /opt/hbase \
    && rm /tmp/hbase.tar.gz

ENV HBASE_HOME=/opt/hbase
ENV PATH="${HBASE_HOME}/bin:${PATH}"

COPY hbase-site.xml ${HBASE_HOME}/conf/hbase-site.xml

EXPOSE 2181 16000 16020

CMD ["bash", "-c", "hbase-daemon.sh start zookeeper && hbase-daemon.sh start master && hbase-daemon.sh start regionserver && exec tail -F ${HBASE_HOME}/logs/*"]
