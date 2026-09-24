// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Attribute rows come from the registry, including attributes nobody emitted.

import {
  LEVELS,
  LEVEL_LABEL,
  attributeUrl,
  distinguish,
  fullLabel,
  languageColor,
  levelColor,
} from "../data.js";
import { el, filterBar, levelLegend, palette, trackBand } from "../ui.js";
import { go, setParams } from "../route.js";

/** The three requirement-level views, the first being the default. */
const LEVEL_CHOICES = [
  { value: "", label: "All levels" },
  { value: "scored", label: "Required + recommended" },
  { value: "required", label: "Required only" },
];

/**
 * Select a signal, falling back to the most frequently emitted signal.
 *
 * @param {import('../data.js').Data} data the indexed report
 * @param {string|null} key a `${type}:${name}` signal key from the route
 * @returns {{available: import('../data.js').Signal[],
 *   chosen: import('../data.js').Signal|undefined, unknown: boolean}}
 */
function choose(data, key) {
  const available = [...data.signals.values()].sort(
    (a, b) => b.rows.length - a.rows.length || a.name.localeCompare(b.name),
  );
  const chosen = key ? data.signals.get(key) : undefined;
  return {
    available,
    chosen: chosen ?? available[0],
    unknown: Boolean(key) && !chosen,
  };
}

/**
 * @param {import('../data.js').Data} data the indexed report
 * @param {string|null} key a `${type}:${name}` signal key from the route
 * @returns {string} the document title for this route
 */
export function title(data, key) {
  const { chosen } = choose(data, key);
  return chosen ? `${chosen.name} · conformance` : "signals · conformance";
}

/**
 * Every signal as a palette entry, grouped by the domain it was read from and
 * ordered inside a domain by how many targets emitted it.
 *
 * @param {import('../data.js').Signal[]} available every signal in the report
 * @returns {import('../ui.js').PaletteItem[]}
 */
function entries(available) {
  const domain = (signal) => signal.rows[0]?.target.domain ?? signal.runner;
  return available
    .slice()
    .sort(
      (a, b) =>
        domain(a).localeCompare(domain(b)) ||
        b.rows.length - a.rows.length ||
        a.name.localeCompare(b.name),
    )
    .map((signal) => ({
      value: signal.key,
      name: signal.name,
      group: domain(signal),
      badge: signal.type,
      count: signal.rows.length,
    }));
}

/**
 * Read the filter state out of a link. The keys are short because they are
 * seen: `?lang=java,go&level=required` is a URL somebody can edit by hand.
 *
 * @param {URLSearchParams} [params] the query on the current route
 * @returns {Object<string,string|string[]>} a {@link filterBar} state
 */
function restore(params) {
  const read = (key) => params?.get(key) ?? "";
  const languages = read("lang");
  return {
    q: read("q"),
    languages: languages ? languages.split(",").filter(Boolean) : [],
    level: read("level"),
    distribution: read("dist"),
    library: read("lib"),
  };
}

/** The inverse of {@link restore}. */
function remember(state) {
  setParams({
    q: state.q,
    lang: state.languages.join(","),
    level: state.level,
    dist: state.distribution,
    lib: state.library,
  });
}

/**
 * Render the signal parity heatmap.
 *
 * @param {import('../data.js').Data} data the indexed report
 * @param {string|null} key a `${type}:${name}` signal key from the route
 * @param {URLSearchParams} [params] the filter state on the current route
 * @returns {HTMLElement} the view, to be appended to `<main>`
 */
export default function signals(data, key, params) {
  const { available, chosen, unknown } = choose(data, key);
  if (!available.length) {
    return el("p", { class: "empty", text: "No signals in the report." });
  }

  const facet = (pick) => [...new Set(chosen.rows.map(pick))].sort();
  const body = el("div");

  const picker = palette({
    label: "Signal",
    items: entries(available),
    value: chosen.key,
    onPick: (value) => go(`/signals/${encodeURIComponent(value)}`),
  });

  const bar = filterBar({
    search: "Filter columns by library or language…",
    pills: [
      {
        key: "languages",
        label: "Language",
        options: facet((row) => row.target.language).map((language) => ({
          value: language,
          label: language,
          count: chosen.rows.filter((row) => row.target.language === language)
            .length,
          color: languageColor(language),
        })),
      },
    ],
    segments: [{ key: "level", label: "Levels", options: LEVEL_CHOICES }],
    selects: [
      {
        key: "distribution",
        label: "Distribution",
        all: "All distributions",
        options: facet((row) => row.target.label),
      },
      {
        key: "library",
        label: "Library",
        all: "All libraries",
        options: facet((row) => row.target.instrumented_library),
      },
    ],
    state: restore(params),
    onChange: (state) => {
      remember(state);
      const rows = chosen.rows.filter((row) => {
        if (
          state.languages.length &&
          !state.languages.includes(row.target.language)
        ) {
          return false;
        }
        if (
          state.library &&
          row.target.instrumented_library !== state.library
        ) {
          return false;
        }
        if (state.distribution && row.target.label !== state.distribution) {
          return false;
        }
        if (state.q) {
          const haystack = [
            row.target.instrumented_library,
            row.target.instrumentation_library,
            row.target.language,
            row.target.label,
            row.target.backend ?? "",
            row.target.side ?? "",
          ]
            .join(" ")
            .toLowerCase();
          if (!haystack.includes(state.q)) return false;
        }
        return true;
      });
      const levels =
        state.level === "required"
          ? ["required"]
          : state.level === "scored"
            ? ["required", "recommended"]
            : LEVELS;
      body.replaceChildren(
        heatmap(chosen, rows, levels, data.report.domains?.[chosen.runner]),
      );
      return rows.length === chosen.rows.length
        ? `${rows.length} target${rows.length === 1 ? "" : "s"}`
        : `${rows.length} of ${chosen.rows.length} targets`;
    },
  });

  const declared = chosen.attributes
    ? Object.keys(chosen.attributes).length
    : 0;

  const controls = el("div", { class: "controls" }, [
    el("div", { class: "controls-row" }, [
      el("h2", { text: "Signal" }),
      picker.node,
    ]),
    bar.node,
  ]);
  trackBand(controls);

  return el("div", {}, [
    controls,
    unknown &&
      el("p", { class: "note" }, [
        el("strong", { text: "No such signal in this report: " }),
        el("span", { class: "mono", text: key }),
        ". Showing ",
        el("span", { class: "mono", text: chosen.name }),
        " instead.",
      ]),
    el("details", { class: "lede" }, [
      el("summary", {}, [
        `Rows are the ${declared} attributes the registry declares on this ` +
          `${chosen.type}; columns are the ${chosen.rows.length} targets that ` +
          "emitted it.",
      ]),
      el("p", {
        text:
          "Rows are grouped by requirement level. A filled cell means an " +
          "attribute was observed at least once with an accepted type; it does " +
          "not mean every observation conformed. A blank cell means no accepted " +
          "value was observed. Missing conditional or opt-in attributes are not " +
          "automatically conformance failures.",
      }),
    ]),
    body,
  ]);
}
function heatmap(signal, rows, levels, pin) {
  if (!rows.length) {
    return el("p", { class: "empty", text: "No targets match those filters." });
  }
  if (!signal.attributes) {
    return el("p", {
      class: "empty",
      text:
        "The registry does not declare this signal, so there is nothing to " +
        "compare against.",
    });
  }

  const columns = rows.slice().sort(compareColumns);
  const labels = distinguish(columns.map((row) => row.target));
  const header = el("tr", {}, [
    el("th", { class: "attr", scope: "col", text: "Attribute" }),
    ...columns.map((row) =>
      columnHeader(row.target, labels.get(row.target.id)),
    ),
    el("th", { class: "tally", scope: "col", text: "emitted by" }),
  ]);

  const grouped = new Map(levels.map((level) => [level, []]));
  for (const [attribute, level] of Object.entries(signal.attributes)) {
    if (grouped.has(level)) grouped.get(level).push(attribute);
  }

  // Each requirement level needs a row group for its accessible header.
  const groups = [];
  let drawn = 0;
  for (const level of levels) {
    const attributes = (grouped.get(level) ?? []).sort();
    if (!attributes.length) continue;
    groups.push(
      el("tbody", {}, [
        el("tr", { class: "level-head" }, [
          el("th", { colspan: columns.length + 2, scope: "rowgroup" }, [
            // The heading spans every column, and a cell that wide cannot be
            // held in place on its own, so the text inside it is what sticks.
            el("span", {}, [
              el("i", { style: `background:${levelColor(level)}` }),
              `${LEVEL_LABEL[level] ?? level} · ${attributes.length}`,
            ]),
          ]),
        ]),
        ...attributes.map((attribute) => attributeRow(attribute, columns, pin)),
      ]),
    );
    drawn += attributes.length;
  }

  if (!drawn) {
    return el("p", {
      class: "empty",
      text: "This signal declares no attributes at the selected levels.",
    });
  }

  return el("div", {}, [
    el("div", { class: "scroller" }, [
      el("table", { class: "heatmap" }, [
        el("thead", {}, [languageBands(columns), header]),
        ...groups,
      ]),
    ]),
    levelLegend(levels),
  ]);
}

/** One attribute, across every column, and how many of them carried it. */
function attributeRow(attribute, columns, pin) {
  const emitted = columns.map((row) => row.signal.emitted.includes(attribute));
  const count = emitted.filter(Boolean).length;
  const url = attributeUrl(attribute, pin);
  return el("tr", {}, [
    el("th", { class: "attr", scope: "row" }, [
      url
        ? el("a", { href: url, rel: "noreferrer", text: attribute })
        : attribute,
    ]),
    ...emitted.map((yes, i) =>
      el("td", { class: `cell ${yes ? "cell-yes" : "cell-no"}` }, [
        el("span", {
          text: yes ? "•" : "",
          title: `${fullLabel(columns[i].target)} ${yes ? "emits" : "does not emit"} ${attribute}`,
        }),
      ]),
    ),
    el("td", { class: "num rowcount", text: `${count}/${columns.length}` }),
  ]);
}

/**
 * Keep the library and qualifiers separate so the rotated header fits.
 */
function columnHeader(target, label) {
  const full = `${label.full} · ${target.instrumentation_library}`;
  const colour = languageColor(target.language);
  return el(
    "th",
    {
      class: "col",
      scope: "col",
      style: `box-shadow: inset 0 -2px 0 ${colour}`,
    },
    [
      el(
        "span",
        {
          title: full,
          "aria-label": full,
        },
        [
          el("b", { text: label.primary }),
          label.secondary && el("i", { text: label.secondary }),
        ],
      ),
    ],
  );
}

/**
 * A band naming each language over the columns it covers. Column headers carry
 * the library, not the language, so this row is the only thing on the page that
 * names one; it stays even when a single band spans every column.
 */
function languageBands(columns) {
  const groups = [];
  for (const row of columns) {
    const last = groups.at(-1);
    if (last && last.language === row.target.language) last.span += 1;
    else groups.push({ language: row.target.language, span: 1 });
  }
  return el("tr", { class: "band" }, [
    el("th", { class: "attr", scope: "col" }),
    ...groups.map((group) => {
      const colour = languageColor(group.language);
      return el("th", {
        class: "band-cell",
        scope: "colgroup",
        colspan: group.span,
        text: group.language,
        style:
          `color:${colour};` +
          `background:color-mix(in srgb, ${colour} 10%, var(--surface-2));` +
          `box-shadow: inset 0 2px 0 ${colour}`,
      });
    }),
    el("th", { class: "tally", scope: "col" }),
  ]);
}

/**
 * Keep language bands contiguous and instrumentations of each backend adjacent.
 */
function compareColumns(a, b) {
  return (
    a.target.language.localeCompare(b.target.language) ||
    a.target.instrumented_library.localeCompare(
      b.target.instrumented_library,
    ) ||
    (a.target.backend ?? "").localeCompare(b.target.backend ?? "") ||
    a.target.label.localeCompare(b.target.label) ||
    (a.target.side ?? "").localeCompare(b.target.side ?? "")
  );
}
