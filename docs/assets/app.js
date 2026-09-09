// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Hash routes support direct links on GitHub Pages without server rewrites.

import { load } from "./data.js";
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

// A malformed escape in a link should not prevent the report from loading.
function decode(hash) {
  try {
    return decodeURIComponent(hash);
  } catch {
    return "";
  }
}

function resolve(hash) {
  const path = decode(hash.replace(/^#/, "")) || "/";
  for (const route of ROUTES) {
    const found = path.match(route.match);
    if (found) return { route, argument: found[1] ?? null };
  }
  return { route: ROUTES[0], argument: null };
}

function render(data) {
  const { route, argument } = resolve(location.hash);
  let title = `${route.name} · conformance`;
  try {
    main.replaceChildren(route.view.default(data, argument));
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
    addEventListener("hashchange", () => {
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
