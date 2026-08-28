// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// The shell: load the report once, then render whichever view the hash names.
//
// Hash routing rather than paths: Pages has no rewrite rules, so `#/signals/x`
// survives a cold load where `/signals/x` would 404.

import { load } from './data.js';
import { el } from './ui.js';

// A view module exports a default renderer and, optionally, a `title`.
import * as signals from './views/signals.js';

// `#/` is the front door and `#/signals/<key>` is what the selector writes;
// separate entries so the front door can be repointed at a landing view
// without touching the deep link.
const ROUTES = [
  { name: 'signals', match: /^\/?$/, view: signals },
  { name: 'signals', match: /^\/signals(?:\/(.+))?$/, view: signals },
];

const main = document.querySelector('main');

// `decodeURIComponent` throws on a stray percent (`#/signals/50%`). A bad
// address is not an unreadable report, so it falls through to the front door
// rather than letting a URIError escape and read as a failed load.
function decode(hash) {
  try {
    return decodeURIComponent(hash);
  } catch {
    return '';
  }
}

function resolve(hash) {
  const path = decode(hash.replace(/^#/, '')) || '/';
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
      el('p', { class: 'empty', text: `Could not render this view: ${error.message}` }),
    );
  }
  document.title = title;
}

function provenance(data) {
  const pins = Object.entries(data.report.domains).map(
    ([name, pin]) =>
      `${name} → ${pin.registry_repo} @ ${pin.registry_ref.slice(0, 12)}`,
  );
  document.querySelector('#provenance').textContent =
    `${data.targets.length} targets. Registries: ${pins.join('; ')}.`;
}

load()
  .then((data) => {
    provenance(data);
    render(data);
    addEventListener('hashchange', () => {
      render(data);
      scrollTo({ top: 0 });
    });
  })
  .catch((error) => {
    console.error(error);
    main.replaceChildren(
      el('div', { class: 'note' }, [
        el('p', {}, [el('strong', { text: 'The report could not be loaded.' })]),
        el('p', {
          text:
            'The page reads data/conformance.json over fetch, which a browser ' +
            'refuses to do from a file:// URL — the usual cause. Serve the ' +
            'directory instead: python -m http.server -d docs',
        }),
        el('p', { class: 'ver', text: String(error) }),
      ]),
    );
  });
