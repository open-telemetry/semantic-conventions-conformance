// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Hash routes support direct links on GitHub Pages without server rewrites.

import { load } from "./data.js";
import { current } from "./route.js";
import { el } from "./ui.js";

import * as signals from "./views/signals.js";

const ROUTES = [
  { name: "signals", match: /^\/?$/, view: signals },
  { name: "signals", match: /^\/signals(?:\/(.+))?$/, view: signals },
];

const main = document.querySelector("main");

document.querySelector(".skip").addEventListener("click", (event) => {
  event.preventDefault();
  main.focus();
});

function resolve() {
  const { path, params } = current();
  for (const route of ROUTES) {
    const found = path.match(route.match);
    if (found) return { route, argument: found[1] ?? null, params };
  }
  return { route: ROUTES[0], argument: null, params };
}

function render(data) {
  const { route, argument, params } = resolve();
  let title = `${route.name} · conformance`;
  try {
    main.replaceChildren(route.view.default(data, argument, params));
    title = route.view.title?.(data, argument) ?? title;
  } catch (error) {
    console.error(error);
    main.replaceChildren(
      el("p", {
        class: "empty",
        text: `Could not render this view: ${error.message}`,
      }),
    );
  }
  document.title = title;
}

function provenance(data) {
  const pins = Object.entries(data.report.domains).map(
    ([name, pin]) =>
      `${name} → ${pin.registry_repo} @ ${pin.registry_ref.slice(0, 12)}`,
  );
  document.querySelector("#provenance").textContent =
    `${data.targets.length} targets. Registries: ${pins.join("; ")}.`;
}

load()
  .then((data) => {
    provenance(data);
    render(data);
    let path = current().raw;
    addEventListener("hashchange", () => {
      // Filters write themselves into the query, which fires no hashchange;
      // guarding on the path anyway keeps a stray one from wiping the view.
      if (current().raw === path) return;
      path = current().raw;
      render(data);
      scrollTo({ top: 0 });
    });
  })
  .catch((error) => {
    console.error(error);
    main.replaceChildren(
      el("div", { class: "note" }, [
        el("p", {}, [
          el("strong", { text: "The report could not be loaded." }),
        ]),
        location.protocol === "file:" &&
          el("p", {
            text:
              "The page reads data/conformance.json over fetch, which a browser " +
              "refuses to do from a file:// URL. Serve the directory instead: " +
              "python -m http.server -d docs",
          }),
        el("p", { class: "ver", text: String(error) }),
      ]),
    );
  });
