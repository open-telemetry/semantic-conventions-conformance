# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM eclipse-temurin:8-jre-jammy@sha256:d53aa7811eba390450721b1037978605992f5d9467c4af629384f23a49f78436

ARG HBASE_VERSION=2.4.18
ARG HBASE_SHA512=1d90aa46271d262abbebc6b807778353a71743be5c30491bec7ccafd05f2ecf8b3ff5c193addf28efd8d0cae4e1748ee74fdefd97fc8499cb1c163f5a2eed48d

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
