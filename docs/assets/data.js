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
 * Attributes only a signal's refinements declare. That is where an attribute
 * came from, not a level: they are shown in a group of their own and never
 * scored, since the signal does not say which refinement applies.
 */
export const REFINEMENT_LABEL = "Refinement attributes (unscored)";
export const REFINEMENT_COLOR = "var(--refinement)";

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

/** Both destinations spell `.` and `_` as `-`: the documentation in page
 *  paths and anchors, the registry in directory names. */
const dashed = (text) => text.replaceAll(/[._]/g, "-");

/**
 * Where an attribute is documented. opentelemetry.io publishes a page per
 * namespace of the released registry; the incubating GenAI registry is not
 * published there, so `gen_ai.*` goes to the pinned source it was read from.
 *
 * @param {string} attribute a declared attribute, e.g. `http.request.method`
 * @param {Pin} [pin] the registry pin of the runner that declared it
 * @returns {string|null} a URL, or null for `gen_ai.*` without a pin
 */
export function attributeUrl(attribute, pin) {
  const [namespace] = attribute.split(".");
  if (namespace === "gen_ai") {
    if (!pin) return null;
    const { registry_repo: repo, registry_ref: ref, registry_dir: dir } = pin;
    return `https://github.com/${repo}/tree/${ref}/${dir}/${dashed(namespace)}`;
  }
  return (
    "https://opentelemetry.io/docs/specs/semconv/registry/attributes/" +
    `${dashed(namespace)}/#${dashed(attribute)}`
  );
}

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
export const signalKey = (type, name) => `${type}:${name}`;

/**
 * @typedef {object} Signal
 * @property {string} key `${type}:${name}`, as a `#/signals/` link spells it
 * @property {string} name the signal's name in the registry
 * @property {string} type `span`, `metric` or `event`
 * @property {string|null} kind a span's kind, or null
 * @property {string} runner the domain the declaration was read from
 * @property {Object<string,string>|null} attributes declared attribute to
 *   requirement level, or null where no target's registry declares the signal
 * @property {Set<string>} refinementAttributes attributes only its
 *   refinements declare
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
 * @property {{required: Tally, recommended: Tally, findings: number}} summary
 * @property {{id: string, message: string, signal_type?: string, signal_name?: string}[]} findings
 * @property {Object<string,{identity: string[], description: string[]}>} entities
 * @property {string[]} scenario_classes
 * @property {ReportSignal[]} signals
 * @typedef {{attributes: Object<string,string>, kind?: string,
 *   refinements?: Object<string,{attributes: Object<string,string>}>}} Declaration
 * @typedef {{registry_repo: string, registry_ref: string,
 *   registry_dir: string}} Pin one runner's registry pin
 * @typedef {object} Report
 * @property {number} schema_version
 * @property {Target[]} targets
 * @property {Object<string,Object<string,Object<string,Declaration>>>} registry
 * @property {Object<string,Pin>} domains
 */

/**
 * @typedef {object} Data
 * @property {Report} report the report as committed
 * @property {Target[]} targets `report.targets`, unwrapped
 * @property {Map<string,Target>} byId targets keyed by id
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
          refinementAttributes: new Set(),
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
      // Only base attributes have to agree; refinement fields are merged.
      for (const refinement of Object.values(declared?.refinements ?? {})) {
        for (const name of Object.keys(refinement.attributes)) {
          if (!Object.hasOwn(entry.attributes, name)) {
            entry.refinementAttributes.add(name);
          }
        }
      }
      entry.rows.push({ target, signal });
    }
  }

  return {
    report,
    targets,
    signals,
    byId: new Map(targets.map((target) => [target.id, target])),
  };
}

function sameAttributes(left, right) {
  if (left === null || right === null) return left === right;
  return (
    Object.keys(left).length === Object.keys(right).length &&
    Object.entries(left).every(([name, level]) => right[name] === level)
  );
}

/**
 * Name a target as a heatmap column: its library, what sets it apart from the
 * library's other targets (its backend, and its side when `sided`), and its
 * distribution. The distribution's common `opentelemetry-` prefix is shortened
 * to `otel-`, and to just `otel` when the rest only repeats the library.
 *
 * @param {Target} target one report target
 * @param {boolean} sided whether the columns shown together differ in side
 * @returns {{library: string, qualifier: string, distribution: string}}
 */
export function columnName(target, sided) {
  const library = target.instrumented_library;
  const qualifier = [target.backend, sided && target.side]
    .filter(Boolean)
    .join(" · ");
  const distribution =
    target.label === `opentelemetry-${library}`
      ? "otel"
      : target.label.replace(/^opentelemetry-/, "otel-");
  return { library, qualifier, distribution };
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

/** @param {Tally} tally @returns {number|null} */
export const ratio = (tally) =>
  tally?.declared ? tally.emitted / tally.declared : null;
