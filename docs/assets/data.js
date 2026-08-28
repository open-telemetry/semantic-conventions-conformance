// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// The report, and the indices every view reads it through.
//
// Built in memory rather than precomputed into the file, so the report stays
// one shape: it says what was observed, and derived answers cannot drift from
// it.

/** Requirement levels, ordered by how much an absence from one means. */
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

export const levelColor = (level) => `var(${LEVEL_VAR[level] ?? '--optin'})`;

/**
 * A stable colour per language, assigned by sorted name rather than by first
 * appearance so it is the same colour on every view. Filled in by `index()`,
 * so `languageColor` only answers after `load()`.
 */
const LANGUAGE_SLOT = new Map();

/** How many `--lang-N` tokens `style.css` defines. */
const LANGUAGE_SLOTS = 6;

export const languageColor = (language) =>
  `var(--lang-${LANGUAGE_SLOT.get(language) ?? LANGUAGE_SLOTS})`;

async function fetchJson(url) {
  const response = await fetch(url, { cache: 'no-cache' });
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return response.json();
}

/**
 * The report shape this file knows how to read. The level vocabulary above is
 * the report's, restated here because the site cannot import Python — so a
 * rename upstream has to fail loudly rather than render every bar as zero.
 */
const SCHEMA_VERSION = 1;

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

/** How a signal is addressed — in the index below, and in a `#/signals/` link. */
const signalKey = (type, name) => `${type}:${name}`;

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
 * where the set mixes both. Computed per set — what distinguishes a target is
 * a fact about its company, not about the target.
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

/** Everything about a target's identity, for a tooltip or a label. */
export function fullLabel(target) {
  const side = target.side ? ` ${target.side}` : '';
  return `${target.instrumented_library} · ${target.label}${side}`;
}
