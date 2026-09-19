// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// The hash carries both the route and the filter state, so a filtered view is
// a link someone can paste into an issue. The two halves are written
// differently on purpose: a route change goes through `location.hash` and
// re-renders, while a filter change is replaced in place, so typing in the
// search box does not rebuild the view under the caret.

// A malformed escape in a link should not prevent the report from loading.
function decode(text) {
  try {
    return decodeURIComponent(text);
  } catch {
    return "";
  }
}

/**
 * @param {string} hash a `location.hash`, with or without its `#`
 * @returns {{raw: string, path: string, params: URLSearchParams}} the path as
 *   written, the same path decoded, and the query string after it
 */
export function split(hash) {
  const text = hash.replace(/^#/, "");
  const cut = text.indexOf("?");
  const raw = cut === -1 ? text : text.slice(0, cut);
  return {
    raw,
    path: decode(raw) || "/",
    params: new URLSearchParams(cut === -1 ? "" : text.slice(cut + 1)),
  };
}

/** @returns {{raw: string, path: string, params: URLSearchParams}} */
export const current = () => split(location.hash);

/**
 * Navigate, dropping the filter state that belonged to the previous view.
 *
 * @param {string} path a route path, its segments already escaped
 */
export function go(path) {
  location.hash = `#${path}`;
}

/**
 * Record filter state on the current route without re-rendering. Empty values
 * are dropped, so an unfiltered view keeps a clean URL.
 *
 * @param {Object<string,string>} values the query to write
 */
export function setParams(values) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value) params.set(key, value);
  }
  const { raw } = current();
  const query = params.toString();
  const next = query ? `#${raw}?${query}` : raw ? `#${raw}` : "";
  if (next === location.hash) return;
  history.replaceState(null, "", next || location.pathname + location.search);
}
