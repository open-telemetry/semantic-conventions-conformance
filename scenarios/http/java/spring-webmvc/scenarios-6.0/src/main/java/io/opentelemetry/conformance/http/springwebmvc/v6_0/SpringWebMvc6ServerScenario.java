/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.springwebmvc.v6_0;

import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.http.HttpContract.Response;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import jakarta.servlet.DispatcherType;
import jakarta.servlet.Filter;
import jakarta.servlet.http.HttpServletRequest;
import org.apache.catalina.Context;
import org.apache.catalina.Wrapper;
import org.apache.catalina.startup.Tomcat;
import org.apache.tomcat.util.descriptor.web.FilterDef;
import org.apache.tomcat.util.descriptor.web.FilterMap;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.event.ContextRefreshedEvent;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.context.WebApplicationContext;
import org.springframework.web.context.support.AnnotationConfigWebApplicationContext;
import org.springframework.web.servlet.DispatcherServlet;
import org.springframework.web.servlet.config.annotation.EnableWebMvc;

/** Hosts the shared HTTP exchanges on Spring Web MVC 6 until the driver says stop. */
public final class SpringWebMvc6ServerScenario {
  private SpringWebMvc6ServerScenario() {}

  public static void run(Filter telemetryFilter) throws Exception {
    Tomcat tomcat = new Tomcat();
    tomcat.setHostname("127.0.0.1");
    tomcat.setPort(HttpServerWorkload.scenarioPort());
    tomcat.getConnector();

    AnnotationConfigWebApplicationContext applicationContext =
        new AnnotationConfigWebApplicationContext();
    applicationContext.register(ConformanceConfiguration.class);

    Context context = tomcat.addContext("", System.getProperty("java.io.tmpdir"));
    applicationContext.setServletContext(context.getServletContext());
    applicationContext.refresh();
    DispatcherServlet dispatcherServlet = new DispatcherServlet(applicationContext);
    applicationContext.getBeanFactory().registerSingleton("dispatcherServlet", dispatcherServlet);
    context
        .getServletContext()
        .setAttribute(
            WebApplicationContext.ROOT_WEB_APPLICATION_CONTEXT_ATTRIBUTE, applicationContext);
    Wrapper dispatcher = Tomcat.addServlet(context, "dispatcher", dispatcherServlet);
    dispatcher.setLoadOnStartup(1);
    context.addServletMappingDecoded("/", "dispatcher");
    addFilter(context, telemetryFilter);

    tomcat.start();
    applicationContext.publishEvent(new ContextRefreshedEvent(applicationContext));
    try {
      ScenarioLifecycle.waitForEof();
    } finally {
      tomcat.stop();
      tomcat.destroy();
      applicationContext.close();
    }
  }

  private static void addFilter(Context context, Filter filter) {
    FilterDef definition = new FilterDef();
    definition.setFilterName("opentelemetry");
    definition.setFilter(filter);
    definition.setAsyncSupported("true");
    context.addFilterDef(definition);

    FilterMap mapping = new FilterMap();
    mapping.setFilterName("opentelemetry");
    mapping.addURLPattern("/*");
    mapping.setDispatcher(DispatcherType.REQUEST.name());
    context.addFilterMapBefore(mapping);
  }

  @Configuration
  @EnableWebMvc
  static class ConformanceConfiguration {
    @Bean
    ConformanceController conformanceController() {
      return new ConformanceController();
    }
  }

  /** The contract's exchanges, declared as Spring Web MVC request mappings. */
  @RestController
  static class ConformanceController {
    @GetMapping("/health")
    ResponseEntity<String> health(HttpServletRequest request) {
      return answer(request, null);
    }

    @GetMapping("/users/{userId}")
    ResponseEntity<String> getUser(HttpServletRequest request) {
      return answer(request, null);
    }

    @PostMapping("/items")
    ResponseEntity<String> createItem(
        HttpServletRequest request, @RequestBody(required = false) String body) {
      return answer(request, body);
    }

    @GetMapping("/status/{code}")
    ResponseEntity<String> status(HttpServletRequest request) {
      return answer(request, null);
    }

    private static ResponseEntity<String> answer(HttpServletRequest request, String body) {
      Response response =
          HttpServerWorkload.respond(
              request.getMethod(),
              request.getRequestURI(),
              body == null || body.isEmpty() ? null : body);
      return ResponseEntity.status(response.statusCode())
          .header(HttpHeaders.CONTENT_TYPE, HttpContract.CONTENT_TYPE)
          .body(response.body());
    }
  }
}
