/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.netty;

import io.netty.bootstrap.Bootstrap;
import io.netty.buffer.ByteBuf;
import io.netty.buffer.Unpooled;
import io.netty.channel.Channel;
import io.netty.channel.ChannelHandlerContext;
import io.netty.channel.ChannelInitializer;
import io.netty.channel.ChannelPipeline;
import io.netty.channel.EventLoopGroup;
import io.netty.channel.SimpleChannelInboundHandler;
import io.netty.channel.nio.NioEventLoopGroup;
import io.netty.channel.socket.SocketChannel;
import io.netty.channel.socket.nio.NioSocketChannel;
import io.netty.handler.codec.http.DefaultFullHttpRequest;
import io.netty.handler.codec.http.FullHttpResponse;
import io.netty.handler.codec.http.HttpClientCodec;
import io.netty.handler.codec.http.HttpHeaderNames;
import io.netty.handler.codec.http.HttpMethod;
import io.netty.handler.codec.http.HttpObjectAggregator;
import io.netty.handler.codec.http.HttpUtil;
import io.netty.handler.codec.http.HttpVersion;
import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;

/** Runs the shared request contract through a raw Netty client pipeline. */
public final class NettyClientScenario {
  // Contract payloads are under 1 KiB; this leaves room for future cases without unbounded
  // buffering.
  private static final int MAX_AGGREGATED_CONTENT_LENGTH = 64 * 1024;

  private NettyClientScenario() {}

  public static void run() throws Exception {
    run(pipeline -> {}, channel -> {});
  }

  public static void run(
      Consumer<ChannelPipeline> pipelineCustomizer, Consumer<Channel> requestCustomizer)
      throws Exception {
    EventLoopGroup group = new NioEventLoopGroup(1);
    try {
      HttpClientWorkload.drive(
          ScenarioEnvironment.require("MOCK_SERVER_URL"),
          (method, url, body) -> {
            URI uri = URI.create(url);
            CompletableFuture<HttpContract.Response> answer = new CompletableFuture<>();

            Channel channel =
                new Bootstrap()
                    .group(group)
                    .channel(NioSocketChannel.class)
                    .handler(
                        new ChannelInitializer<SocketChannel>() {
                          @Override
                          protected void initChannel(SocketChannel socketChannel) {
                            ChannelPipeline pipeline = socketChannel.pipeline();
                            pipeline.addLast(new HttpClientCodec());
                            pipelineCustomizer.accept(pipeline);
                            pipeline
                                .addLast(new HttpObjectAggregator(MAX_AGGREGATED_CONTENT_LENGTH))
                                .addLast(new ResponseHandler(answer));
                          }
                        })
                    .connect(uri.getHost(), uri.getPort())
                    .sync()
                    .channel();

            requestCustomizer.accept(channel);
            channel.writeAndFlush(request(HttpMethod.valueOf(method), uri, body)).sync();
            try {
              return answer.get(
                  HttpClientWorkload.REQUEST_TIMEOUT.toMillis(), TimeUnit.MILLISECONDS);
            } finally {
              channel.close().sync();
            }
          });
    } finally {
      group.shutdownGracefully().sync();
    }
  }

  private static DefaultFullHttpRequest request(HttpMethod method, URI uri, String body) {
    String target = uri.getRawPath();
    if (uri.getRawQuery() != null) {
      target += "?" + uri.getRawQuery();
    }

    ByteBuf content =
        body == null ? Unpooled.EMPTY_BUFFER : Unpooled.copiedBuffer(body, StandardCharsets.UTF_8);
    DefaultFullHttpRequest request =
        new DefaultFullHttpRequest(HttpVersion.HTTP_1_1, method, target, content);
    request.headers().set(HttpHeaderNames.HOST, uri.getHost() + ":" + uri.getPort());
    request.headers().set(HttpHeaderNames.USER_AGENT, HttpContract.USER_AGENT);
    if (body != null) {
      request.headers().set(HttpHeaderNames.CONTENT_TYPE, HttpContract.CONTENT_TYPE);
    }
    HttpUtil.setContentLength(request, content.readableBytes());
    return request;
  }

  private static final class ResponseHandler extends SimpleChannelInboundHandler<FullHttpResponse> {
    private final CompletableFuture<HttpContract.Response> answer;

    ResponseHandler(CompletableFuture<HttpContract.Response> answer) {
      this.answer = answer;
    }

    @Override
    protected void channelRead0(ChannelHandlerContext context, FullHttpResponse response) {
      answer.complete(
          new HttpContract.Response(
              response.status().code(), response.content().toString(StandardCharsets.UTF_8)));
    }

    @Override
    public void exceptionCaught(ChannelHandlerContext context, Throwable cause) {
      answer.completeExceptionally(cause);
      context.close();
    }
  }
}
