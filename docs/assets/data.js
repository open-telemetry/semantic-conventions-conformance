// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// The report is written by `otel-conformance-report build`. Its output types
// are defined in `tools/report/src/conformance_report/_types.py`.

/**
 * Requirement levels from the registry. Scoring is defined by `SCORED_LEVELS`
 * in `tools/report/src/conformance_report/_aggregate.py`.
 */
export const LEVELS = [
  "required",
  "conditionally_required_conditional",
  "recommended",
  "recommended_conditional",
  "opt_in",
];

export const LEVEL_LABEL = {
  required: "Required",
  conditionally_required_conditional: "Conditionally required",
  recommended: "Recommended",
  recommended_conditional: "Recommended (conditional)",
  opt_in: "Opt-in",
};

const LEVEL_VAR = {
  required: "--required",
  conditionally_required_conditional: "--conditional",
  recommended: "--recommended",
  recommended_conditional: "--conditional",
  opt_in: "--optin",
};

/**
 * @param {string} level a requirement level from {@link LEVELS}
 * @returns {string} a CSS `var()` reference to that level's colour
 */
export const levelColor = (level) => `var(${LEVEL_VAR[level] ?? "--optin"})`;

/**
 * Assigned in sorted language order when the report is indexed.
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
  const response = await fetch(url, { cache: "no-cache" });
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return response.json();
}

/**
 * Copied from `SCHEMA_VERSION` in
 * `tools/report/src/conformance_report/_aggregate.py`.
 */
const SCHEMA_VERSION = 1;

/**
 * Fetch `data/conformance.json` and index it.
 *
 * @returns {Promise<Data>} the indexed report
 * @throws if the fetch fails or the report is a schema this file cannot read
 */
export async function load() {
  const report = await fetchJson("data/conformance.json");
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
 * @property {{target: Target, signal: ReportSignal}[]} rows one per target emitting it
 */

/**
 * Report fields consumed by the site; copied from the Python output types above.
 * @typedef {{emitted: number, declared: number}} Tally
 * @typedef {object} ReportSignal
 * @property {string} type
 * @property {string} name
 * @property {string[]} emitted
 * @property {Object<string,Tally>} [coverage]
 * @property {string[]} [missing]
 * @property {null} [declared]
 * @typedef {object} Target
 * @property {string} id
 * @property {string} path
 * @property {string} domain
 * @property {string} language
 * @property {string} runner
 * @property {string} instrumented_library
 * @property {string} instrumentation_library
 * @property {string} label
 * @property {string|null} side
 * @property {string|null} [backend]
 * @property {ReportSignal[]} signals
 * @typedef {{attributes: Object<string,string>, kind?: string}} Declaration
 * @typedef {object} Report
 * @property {number} schema_version
 * @property {Target[]} targets
 * @property {Object<string,Object<string,Object<string,Declaration>>>} registry
 * @property {Object<string,{registry_repo: string, registry_ref: string, registry_dir: string}>} domains
 */

/**
 * @typedef {object} Data
 * @property {Report} report the report as committed
 * @property {Target[]} targets `report.targets`, unwrapped
 * @property {Map<string,Signal>} signals keyed by `${type}:${name}`
 */

/**
 * @param {Report} report a parsed `data/conformance.json`
 * @returns {Data}
 */
function index(report) {
  const languages = [...new Set(report.targets.map((t) => t.language))].sort();
  LANGUAGE_SLOT.clear();
  languages.forEach((language, i) =>
    LANGUAGE_SLOT.set(language, (i % LANGUAGE_SLOTS) + 1),
  );

  const targets = report.targets;

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
          kind: declared?.kind ?? null,
          runner: target.runner,
          attributes: declared?.attributes ?? null,
          rows: [],
        };
        signals.set(key, entry);
      } else if (
        entry.kind !== (declared?.kind ?? null) ||
        !sameAttributes(entry.attributes, declared?.attributes ?? null)
      ) {
        throw new Error(
          `Conflicting declarations for ${key} in ${entry.runner} and ${target.runner}`,
        );
      }
      entry.rows.push({ target, signal });
    }
  }

  return { report, targets, signals };
}

function sameAttributes(left, right) {
  if (left === null || right === null) return left === right;
  return (
    Object.keys(left).length === Object.keys(right).length &&
    Object.entries(left).every(([name, level]) => right[name] === level)
  );
}

/**
 * Return display labels that distinguish the supplied targets.
 *
 * @param {Target[]} targets the targets being shown together
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
  const sides = new Set(targets.map((target) => target.side ?? ""));

  return new Map(
    targets.map((target) => {
      const parts = [];
      if (target.backend) parts.push(target.backend);
      if (byLibrary.get(target.instrumented_library).size > 1) {
        parts.push(target.label);
      }
      if (sides.size > 1 && target.side) parts.push(target.side);
      return [
        target.id,
        {
          primary: target.instrumented_library,
          secondary: parts.join(" · ") || null,
          full: fullLabel(target),
        },
      ];
    }),
  );
}

/**
 * @param {Target} target one report target
 * @returns {string}
 */
export function fullLabel(target) {
  return [
    target.instrumented_library,
    target.backend,
    target.label,
    target.side,
  ]
    .filter(Boolean)
    .join(" · ");
}
