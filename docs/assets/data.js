// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// The report, and the indices every view reads it through.
//
// The indices are built in memory rather than precomputed into the file, so the
// report keeps one shape and derived answers cannot drift from it.
//
// The report is written by `otel-conformance-report build`; its shape is defined
// in `tools/report/src/conformance_report/_aggregate.py`.

/**
 * Requirement levels, ordered by how much an absence from one means.
 *
 * The vocabulary is the registry's. Which of these are scored is decided by
 * `SCORED_LEVELS` in `tools/report/src/conformance_report/_aggregate.py`.
 */
export const LEVELS = [
  'required',
  'conditionally_required_conditional',
  'recommended',
  'recommended_conditional',
  'opt_in',
];

export const LEVEL_LABEL = {
  required: 'Required',
  conditionally_required_conditional: 'Conditionally required',
  recommended: 'Recommended',
  recommended_conditional: 'Recommended (conditional)',
  opt_in: 'Opt-in',
};

const LEVEL_VAR = {
  required: '--required',
  conditionally_required_conditional: '--conditional',
  recommended: '--recommended',
  recommended_conditional: '--conditional',
  opt_in: '--optin',
};

/**
 * @param {string} level a requirement level from {@link LEVELS}
 * @returns {string} a CSS `var()` reference to that level's colour
 */
export const levelColor = (level) => `var(${LEVEL_VAR[level] ?? '--optin'})`;

/**
 * A stable colour per language, assigned by sorted name rather than by first
 * appearance so it is the same colour on every view. Filled in by `index()`,
 * so `languageColor` only answers after `load()`.
 */
const LANGUAGE_SLOT = new Map();

/** How many `--lang-N` tokens `style.css` defines. */
const LANGUAGE_SLOTS = 6;

/**
 * @param {string} language a target's `language` facet
 * @returns {string} a CSS `var()` reference to that language's colour
 */
export const languageColor = (language) =>
  `var(--lang-${LANGUAGE_SLOT.get(language) ?? LANGUAGE_SLOTS})`;

async function fetchJson(url) {
  const response = await fetch(url, { cache: 'no-cache' });
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return response.json();
}

/**
 * The report shape this file knows how to read.
 *
 * The source of truth is `SCHEMA_VERSION` in
 * `tools/report/src/conformance_report/_aggregate.py`. The site cannot import
 * Python, so the constant is duplicated here and checked on load: a rename
 * upstream fails loudly rather than rendering every bar as zero.
 */
const SCHEMA_VERSION = 1;

/**
 * Fetch `data/conformance.json` and index it.
 *
 * @returns {Promise<Data>} the indexed report
 * @throws if the fetch fails or the report is a schema this file cannot read
 */
export async function load() {
  const report = await fetchJson('data/conformance.json');
  if (report.schema_version !== SCHEMA_VERSION) {
    throw new Error(
      `data/conformance.json is schema_version ${report.schema_version}; ` +
        `this page reads ${SCHEMA_VERSION}`,
    );
  }
  return index(report);
}

/** How a signal is addressed, in the index below and in a `#/signals/` link. */
const signalKey = (type, name) => `${type}:${name}`;

/**
 * @typedef {object} Signal
 * @property {string} key `${type}:${name}`, as a `#/signals/` link spells it
 * @property {string} name the signal's name in the registry
 * @property {string} type `span`, `metric` or `event`
 * @property {string|null} kind a span's kind, or null
 * @property {string} runner the domain the declaration was read from
 * @property {Object<string,string>|null} attributes declared attribute to
 *   requirement level, or null where no target's registry declares the signal
 * @property {{target: object, signal: object}[]} rows one per target emitting it
 */

/**
 * @typedef {object} Data
 * @property {object} report the report as committed
 * @property {object[]} targets `report.targets`, unwrapped
 * @property {Map<string,Signal>} signals keyed by `${type}:${name}`
 */

/**
 * @param {object} report a parsed `data/conformance.json`
 * @returns {Data}
 */
function index(report) {
  const languages = [...new Set(report.targets.map((t) => t.language))].sort();
  LANGUAGE_SLOT.clear();
  languages.forEach((language, i) =>
    LANGUAGE_SLOT.set(language, (i % LANGUAGE_SLOTS) + 1),
  );

  const targets = report.targets;

  // Signals, each with the registry's declaration and everyone who emits it.
  // Keyed by type and name together: a metric and a span may share a name, and
  // the entry carries the declaration every column is drawn against.
  const signals = new Map();
  for (const target of targets) {
    for (const signal of target.signals) {
      const declared =
        report.registry?.[target.runner]?.[`${signal.type}s`]?.[signal.name] ??
        null;
      const key = signalKey(signal.type, signal.name);
      let entry = signals.get(key);
      if (!entry) {
        entry = {
          key,
          name: signal.name,
          type: signal.type,
          kind: null,
          runner: target.runner,
          attributes: null,
          rows: [],
        };
        signals.set(key, entry);
      }
      // First declaration wins, but an absent one never does.
      if (entry.attributes === null && declared?.attributes) {
        entry.attributes = declared.attributes;
        entry.kind = declared.kind ?? null;
        entry.runner = target.runner;
      }
      entry.rows.push({ target, signal });
    }
  }

  return { report, targets, signals };
}

/**
 * The least that still tells a set of targets apart: the library, plus the
 * report's `label` only where two of them share a library, plus the side only
 * where the set mixes both. Computed per set, because what distinguishes a
 * target depends on which others it is shown beside.
 *
 * @param {object[]} targets the targets being shown together
 * @returns {Map<string,{primary: string, secondary: string|null, full: string}>}
 *   keyed by `target.id`
 */
export function distinguish(targets) {
  const byLibrary = new Map();
  for (const target of targets) {
    const key = target.instrumented_library;
    if (!byLibrary.has(key)) byLibrary.set(key, new Set());
    byLibrary.get(key).add(target.label);
  }
  const sides = new Set(targets.map((target) => target.side ?? ''));

  return new Map(
    targets.map((target) => {
      const parts = [];
      if (byLibrary.get(target.instrumented_library).size > 1) {
        parts.push(target.label);
      }
      if (sides.size > 1 && target.side) parts.push(target.side);
      return [
        target.id,
        {
          primary: target.instrumented_library,
          secondary: parts.join(' · ') || null,
          full: fullLabel(target),
        },
      ];
    }),
  );
}

/**
 * Everything about a target's identity, for a tooltip or a label.
 *
 * @param {object} target one report target
 * @returns {string}
 */
export function fullLabel(target) {
  const side = target.side ? ` ${target.side}` : '';
  return `${target.instrumented_library} · ${target.label}${side}`;
}
