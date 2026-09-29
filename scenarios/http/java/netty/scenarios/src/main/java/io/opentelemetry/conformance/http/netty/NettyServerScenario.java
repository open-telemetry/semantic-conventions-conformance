/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.netty;

import io.netty.bootstrap.ServerBootstrap;
import io.netty.buffer.ByteBuf;
import io.netty.buffer.Unpooled;
import io.netty.channel.Channel;
import io.netty.channel.ChannelFuture;
import io.netty.channel.ChannelFutureListener;
import io.netty.channel.ChannelHandlerContext;
import io.netty.channel.ChannelInitializer;
import io.netty.channel.ChannelPipeline;
import io.netty.channel.EventLoopGroup;
import io.netty.channel.SimpleChannelInboundHandler;
import io.netty.channel.nio.NioEventLoopGroup;
import io.netty.channel.socket.SocketChannel;
import io.netty.channel.socket.nio.NioServerSocketChannel;
import io.netty.handler.codec.http.DefaultFullHttpResponse;
import io.netty.handler.codec.http.FullHttpRequest;
import io.netty.handler.codec.http.FullHttpResponse;
import io.netty.handler.codec.http.HttpHeaderNames;
import io.netty.handler.codec.http.HttpObjectAggregator;
import io.netty.handler.codec.http.HttpResponseStatus;
import io.netty.handler.codec.http.HttpServerCodec;
import io.netty.handler.codec.http.HttpUtil;
import io.netty.handler.codec.http.HttpVersion;
import io.netty.handler.codec.http.QueryStringDecoder;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.http.HttpContract.Response;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.function.Consumer;

/**
 * Hosts the shared HTTP exchanges on a raw Netty pipeline until the driver says stop.
 *
 * <p>Netty has no routing model, so the handler dispatches on the concrete path: matching by
 * request rather than declaring templates is the framework's own form here, and an instrumentation
 * therefore has no route to read.
 */
public final class NettyServerScenario {
  // Contract payloads are under 1 KiB; this leaves room for future cases without unbounded
  // buffering.
  private static final int MAX_AGGREGATED_CONTENT_LENGTH = 64 * 1024;

  private NettyServerScenario() {}

  public static void run() throws Exception {
    run(pipeline -> {});
  }

  public static void run(Consumer<ChannelPipeline> pipelineCustomizer) throws Exception {
    EventLoopGroup group = new NioEventLoopGroup(1);
    try {
      Channel channel =
          new ServerBootstrap()
              .group(group)
              .channel(NioServerSocketChannel.class)
              .childHandler(
                  new ChannelInitializer<SocketChannel>() {
                    @Override
                    protected void initChannel(SocketChannel socketChannel) {
                      ChannelPipeline pipeline = socketChannel.pipeline();
                      pipeline.addLast(new HttpServerCodec());
                      pipelineCustomizer.accept(pipeline);
                      pipeline
                          .addLast(new HttpObjectAggregator(MAX_AGGREGATED_CONTENT_LENGTH))
                          .addLast(new ConformanceHandler());
                    }
                  })
              .bind(new InetSocketAddress("127.0.0.1", HttpServerWorkload.scenarioPort()))
              .sync()
              .channel();

      try {
        ScenarioLifecycle.waitForEof();
      } finally {
        channel.close().sync();
      }
    } finally {
      group.shutdownGracefully().sync();
    }
  }

  private static final class ConformanceHandler
      extends SimpleChannelInboundHandler<FullHttpRequest> {
    @Override
    protected void channelRead0(ChannelHandlerContext context, FullHttpRequest request) {
      String requestBody = request.content().toString(StandardCharsets.UTF_8);
      Response answer =
          HttpServerWorkload.respond(
              request.method().name(),
              new QueryStringDecoder(request.uri()).path(),
              requestBody.isEmpty() ? null : requestBody);

      ByteBuf content = Unpooled.copiedBuffer(answer.body(), StandardCharsets.UTF_8);
      FullHttpResponse response =
          new DefaultFullHttpResponse(
              HttpVersion.HTTP_1_1, HttpResponseStatus.valueOf(answer.statusCode()), content);
      response.headers().set(HttpHeaderNames.CONTENT_TYPE, HttpContract.CONTENT_TYPE);
      HttpUtil.setContentLength(response, content.readableBytes());
      boolean keepAlive = HttpUtil.isKeepAlive(request);
      HttpUtil.setKeepAlive(response, keepAlive);
      ChannelFuture write = context.writeAndFlush(response);
      if (!keepAlive) {
        write.addListener(ChannelFutureListener.CLOSE);
      }
    }

    @Override
    public void exceptionCaught(ChannelHandlerContext context, Throwable cause) {
      context.close();
    }
  }
}
