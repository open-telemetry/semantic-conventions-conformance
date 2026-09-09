// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Attribute rows come from the registry, including attributes nobody emitted.

import {
  LEVELS,
  LEVEL_LABEL,
  distinguish,
  fullLabel,
  languageColor,
  levelColor,
} from "../data.js";
import { el, levelLegend, toolbar } from "../ui.js";

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
 * Render the signal parity heatmap.
 *
 * @param {import('../data.js').Data} data the indexed report
 * @param {string|null} key a `${type}:${name}` signal key from the route
 * @returns {HTMLElement} the view, to be appended to `<main>`
 */
export default function signals(data, key) {
  const { available, chosen, unknown } = choose(data, key);
  if (!available.length) {
    return el("p", { class: "empty", text: "No signals in the report." });
  }

  const body = el("div");
  const bar = toolbar({
    search: "Filter columns by library or instrumentation…",
    filters: [
      {
        key: "signal",
        label: "Signal",
        all: null,
        value: chosen.key,
        options: available.map((signal) => ({
          value: signal.key,
          label: `${signal.name} (${signal.rows.length})`,
        })),
      },
      {
        key: "level",
        label: "Levels",
        all: "All levels",
        options: [
          { value: "scored", label: "Required + recommended" },
          { value: "required", label: "Required only" },
        ],
      },
      {
        key: "language",
        label: "Language",
        all: "All languages",
        options: [
          ...new Set(chosen.rows.map((row) => row.target.language)),
        ].sort(),
      },
      {
        key: "library",
        label: "Library",
        all: "All libraries",
        options: [
          ...new Set(chosen.rows.map((row) => row.target.instrumented_library)),
        ].sort(),
      },
    ],
    onChange: (state) => {
      if (state.signal && state.signal !== chosen.key) {
        location.hash = `#/signals/${encodeURIComponent(state.signal)}`;
        return "";
      }
      const rows = chosen.rows.filter((row) => {
        if (state.language && row.target.language !== state.language)
          return false;
        if (
          state.library &&
          row.target.instrumented_library !== state.library
        ) {
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
      body.replaceChildren(heatmap(chosen, rows, levels));
      return `${rows.length} target${rows.length === 1 ? "" : "s"}`;
    },
  });

  return el("div", {}, [
    el("h2", {}, [
      "Signal parity: ",
      el("span", { class: "mono", text: chosen.name }),
    ]),
    unknown &&
      el("p", { class: "note" }, [
        el("strong", { text: "No such signal in this report: " }),
        el("span", { class: "mono", text: key }),
        ". Showing ",
        el("span", { class: "mono", text: chosen.name }),
        " instead.",
      ]),
    el("p", {
      class: "lede",
      text:
        `Rows are the ${
          chosen.attributes ? Object.keys(chosen.attributes).length : 0
        } attributes the registry declares on this ${chosen.type}, grouped by ` +
        "requirement level. Columns are targets that emitted the signal. A filled " +
        "cell means an attribute was observed at least once with an accepted type; " +
        "it does not mean every observation conformed. A blank cell means no " +
        "accepted value was observed. Missing conditional or opt-in attributes " +
        "are not automatically conformance failures.",
    }),
    bar.node,
    body,
  ]);
}

function heatmap(signal, rows, levels) {
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
            el("i", { style: `background:${levelColor(level)}` }),
            `${LEVEL_LABEL[level] ?? level} · ${attributes.length}`,
          ]),
        ]),
        ...attributes.map((attribute) => attributeRow(attribute, columns)),
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

  const bands = languageBands(columns);
  return el("div", {}, [
    caption(columns),
    el("div", { class: "scroller fit" }, [
      el("table", { class: `heatmap${bands ? " banded" : ""}` }, [
        el("thead", {}, [bands, header]),
        ...groups,
      ]),
    ]),
    levelLegend(levels),
  ]);
}

/** One attribute, across every column, and how many of them carried it. */
function attributeRow(attribute, columns) {
  const emitted = columns.map((row) => row.signal.emitted.includes(attribute));
  const count = emitted.filter(Boolean).length;
  return el("tr", {}, [
    el("th", { class: "attr", scope: "row", text: attribute }),
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
 * A band naming each language over the columns it covers, or null when they are
 * all one language, which the caption already says.
 */
function languageBands(columns) {
  const groups = [];
  for (const row of columns) {
    const last = groups.at(-1);
    if (last && last.language === row.target.language) last.span += 1;
    else groups.push({ language: row.target.language, span: 1 });
  }
  if (groups.length < 2) return null;
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
 * Return a caption containing only fields shared by all columns.
 */
function caption(columns) {
  const shared = (pick) => {
    const values = new Set(columns.map((row) => pick(row.target)));
    return values.size === 1 ? [...values][0] : null;
  };
  const language = shared((t) => t.language);
  const side = shared((t) => t.side);
  const instrumentation = shared((t) => t.instrumentation_library);

  const parts = [`${columns.length} column${columns.length === 1 ? "" : "s"}`];
  if (language) parts.push(`every one ${language}`);
  if (side) parts.push(`every one ${side}-side`);
  if (instrumentation) parts.push(`all through ${instrumentation}`);
  return el("p", { class: "caption", text: parts.join(" · ") });
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
