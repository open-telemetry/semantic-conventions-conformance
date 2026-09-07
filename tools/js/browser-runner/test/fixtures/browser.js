window
  .fetch(`${window.__otelConformance.baseUrl}/example`)
  .then(async (response) => {
    if ((await response.text()) !== "contract response") {
      throw new Error("the bridge did not proxy the contract response");
    }
    return window.fetch(window.__otelConformance.traceExporterUrl, {
      method: "POST",
      body: new Uint8Array([1, 2, 3]),
    });
  })
  .then(() => {
    window.__otelConformanceResult = { ok: true };
  })
  .catch((error) => {
    window.__otelConformanceResult = { ok: false, error: String(error) };
  });
