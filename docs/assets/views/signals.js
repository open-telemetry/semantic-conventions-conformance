// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Attribute rows come from the registry, including attributes nobody emitted.

import {
  LEVELS,
  LEVEL_LABEL,
  REFINEMENT_COLOR,
  REFINEMENT_LABEL,
  attributeUrl,
  columnName,
  fullLabel,
  languageColor,
  levelColor,
} from "../data.js";
import { el, filterBar, levelLegend, palette } from "../ui.js";
import { go, setParams, signalPath, targetHref } from "../route.js";

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
    onPick: (value) => go(signalPath(value)),
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
      const refinements = state.level
        ? []
        : [...chosen.refinementAttributes].sort();
      body.replaceChildren(
        heatmap(
          chosen,
          rows,
          levels,
          refinements,
          data.report.domains?.[chosen.runner],
        ),
      );
      return rows.length === chosen.rows.length
        ? `${rows.length} target${rows.length === 1 ? "" : "s"}`
        : `${rows.length} of ${chosen.rows.length} targets`;
    },
  });

  const declared = chosen.attributes
    ? Object.keys(chosen.attributes).length
    : 0;
  const refined = chosen.refinementAttributes.size;

  const controls = el("div", { class: "controls unpinned" }, [
    el("div", { class: "controls-row" }, [
      el("h2", { text: "Signal" }),
      picker.node,
    ]),
    bar.node,
  ]);

  return el("div", {}, [
    controls,
    el("p", {
      class: "tagline",
      text: "What instrumentations actually emit, measured through Weaver live-check against the pinned registries.",
    }),
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
          `${chosen.type}` +
          (refined ? `, plus ${refined} more its refinements declare` : "") +
          `; columns are the ${chosen.rows.length} targets that emitted it.`,
      ]),
      el("p", {
        text:
          "Rows are grouped by requirement level. A filled cell means an " +
          "attribute was observed at least once with an accepted type; it does " +
          "not mean every observation conformed. A blank cell means no accepted " +
          "value was observed. Missing conditional or opt-in attributes are not " +
          "automatically conformance failures. Refinement attributes are shown " +
          "without a score, since the signal does not identify which refinement " +
          "applies. Their blank cells do not establish a conformance gap.",
      }),
    ]),
    body,
  ]);
}
function heatmap(signal, rows, levels, refinements, pin) {
  dispose();
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
  const sided = new Set(columns.map((row) => row.target.side ?? "")).size > 1;
  const header = el("tr", {}, [
    el("th", { class: "attr", scope: "col", text: "Attribute" }),
    ...columns.map((row) => columnHeader(row.target, sided)),
    el("th", { class: "tally", scope: "col" }, [
      el("span", { class: "upright", text: "emitted by" }),
    ]),
  ]);

  const grouped = new Map(levels.map((level) => [level, []]));
  for (const [attribute, level] of Object.entries(signal.attributes)) {
    if (grouped.has(level)) grouped.get(level).push(attribute);
  }

  // Each requirement level needs a row group for its accessible header.
  const groups = [];
  let drawn = 0;
  const group = (color, label, attributes) => {
    if (!attributes.length) return;
    groups.push(
      el("tbody", {}, [
        el("tr", { class: "level-head" }, [
          el("th", { colspan: columns.length + 2, scope: "rowgroup" }, [
            // The heading spans every column, and a cell that wide cannot be
            // held in place on its own, so the text inside it is what sticks.
            el("span", {}, [
              el("i", { style: `background:${color}` }),
              `${label} · ${attributes.length}`,
            ]),
          ]),
        ]),
        ...attributes.map((attribute) => attributeRow(attribute, columns, pin)),
      ]),
    );
    drawn += attributes.length;
  };
  for (const level of levels) {
    group(
      levelColor(level),
      LEVEL_LABEL[level] ?? level,
      (grouped.get(level) ?? []).sort(),
    );
  }
  group(REFINEMENT_COLOR, REFINEMENT_LABEL, refinements);

  if (!drawn) {
    return el("p", {
      class: "empty",
      text: "This signal declares no attributes at the selected levels.",
    });
  }

  const scroller = el("div", { class: "scroller" }, [
    el("table", { class: "heatmap" }, [
      el("thead", {}, [header, languageBands(columns)]),
      ...groups,
    ]),
  ]);
  const rail = el(
    "div",
    { class: "scroll-rail", "aria-hidden": "true", tabindex: "-1" },
    [el("div")],
  );
  const frame = el("div", { class: "scroll-frame" }, [scroller, rail]);
  trackEdges(frame, scroller, rail);
  return el("div", {}, [frame, levelLegend(levels, refinements.length > 0)]);
}

let stopTrackingEdges = null;

export function dispose() {
  stopTrackingEdges?.();
  stopTrackingEdges = null;
}

/**
 * Flag the sides of the frame that have columns scrolled past them, or `fits`
 * when there are none, and publish `--pinned-w`, the pinned attribute column's
 * width, where the left shadow starts. The rail is a scrollbar held at the
 * bottom of the screen, kept as wide as the table and in step with it, since
 * the table's own is past the last row. Moving the existing header vertically
 * keeps it aligned with the columns inside the horizontal scroller.
 */
function trackEdges(frame, scroller, rail) {
  const table = scroller.firstElementChild;
  const header = table.querySelector("thead");
  const pinned = table.querySelector("th.attr");
  let end = 0;
  let stickyHeader = false;
  let maxHeaderOffset = 0;
  let headerOffset = 0;
  const updateHeader = () => {
    const offset = stickyHeader
      ? Math.max(
          0,
          Math.min(maxHeaderOffset, -table.getBoundingClientRect().top),
        )
      : 0;
    if (offset !== headerOffset) {
      headerOffset = offset;
      header.style.setProperty("--header-offset", `${offset}px`);
    }
  };
  const updatePosition = () => {
    frame.classList.toggle("more-left", scroller.scrollLeft > 1);
    frame.classList.toggle("more-right", scroller.scrollLeft < end - 1);
    if (rail.scrollLeft !== scroller.scrollLeft) {
      rail.scrollLeft = scroller.scrollLeft;
    }
  };
  const measure = () => {
    const width = scroller.scrollWidth;
    end = width - scroller.clientWidth;
    const headerHeight = header.offsetHeight;
    const viewportHeight = document.documentElement.clientHeight;
    const pinnedWidth = pinned?.offsetWidth ?? 0;
    maxHeaderOffset = Math.max(0, table.offsetHeight - headerHeight);
    stickyHeader = headerHeight > 0 && headerHeight <= viewportHeight / 3;
    frame.classList.toggle("fits", end <= 1);
    frame.classList.toggle("sticky-header", stickyHeader);
    frame.style.setProperty("--pinned-w", `${pinnedWidth}px`);
    rail.firstElementChild.style.width = `${width}px`;
    updatePosition();
    updateHeader();
  };
  const scrollRail = () => {
    if (scroller.scrollLeft !== rail.scrollLeft) {
      scroller.scrollLeft = rail.scrollLeft;
    }
  };
  scroller.addEventListener("scroll", updatePosition, { passive: true });
  rail.addEventListener("scroll", scrollRail, { passive: true });
  addEventListener("resize", measure, { passive: true });
  addEventListener("scroll", updateHeader, { passive: true });
  let observer;
  let timer;
  if (typeof ResizeObserver === "function") {
    observer = new ResizeObserver(measure);
    observer.observe(scroller);
    observer.observe(table);
    observer.observe(header);
  } else {
    timer = setTimeout(measure, 0);
  }
  stopTrackingEdges = () => {
    observer?.disconnect();
    clearTimeout(timer);
    removeEventListener("resize", measure);
    removeEventListener("scroll", updateHeader);
    scroller.removeEventListener("scroll", updatePosition);
    rail.removeEventListener("scroll", scrollRail);
  };
}

/** One attribute, across every column, and how many of them carried it. */
function attributeRow(attribute, columns, pin) {
  const emitted = columns.map((row) => row.signal.emitted.includes(attribute));
  const count = emitted.filter(Boolean).length;
  const url = attributeUrl(attribute, pin);
  // The namespace is muted, so the part that differs between neighbours
  // stands out.
  const leaf = attribute.lastIndexOf(".") + 1;
  const name = [
    leaf > 0 && el("span", { class: "ns", text: attribute.slice(0, leaf) }),
    attribute.slice(leaf),
  ];
  return el("tr", {}, [
    el("th", { class: "attr", scope: "row" }, [
      url
        ? el("a", { href: url, rel: "noreferrer" }, name)
        : el("span", {}, name),
    ]),
    ...emitted.map((yes, i) =>
      el("td", { class: `cell ${yes ? "cell-yes" : "cell-no"}` }, [
        el("span", {
          title: `${fullLabel(columns[i].target)} ${yes ? "emits" : "does not emit"} ${attribute}`,
        }),
      ]),
    ),
    el("td", { class: "num rowcount", text: `${count}/${columns.length}` }),
  ]);
}

/**
 * A target named on two lines, read up from the foot of its column. The
 * library leads, followed by its qualifier and distribution. The link's
 * accessible name and tooltip carry the whole label.
 */
function columnHeader(target, sided) {
  const full = `${fullLabel(target)} · ${target.instrumentation_library}`;
  const name = columnName(target, sided);
  return el("th", { class: "col", scope: "col" }, [
    el(
      "a",
      {
        class: "upright",
        href: targetHref(target.id),
        title: full,
        "aria-label": full,
      },
      [
        el("b", { text: name.library }),
        el("span", { class: "secondary" }, [
          name.qualifier && `${name.qualifier} · `,
          el("i", { text: name.distribution }),
        ]),
      ],
    ),
  ]);
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
      return el(
        "th",
        {
          class: "band-cell",
          scope: "colgroup",
          colspan: group.span,
          title: group.language,
          style:
            `color:${colour};` +
            `background:color-mix(in srgb, ${colour} 10%, var(--surface-2));` +
            `box-shadow: inset 0 2px 0 ${colour}`,
        },
        // The name is clipped to the band rather than widening its columns.
        [el("span", { text: group.language })],
      );
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
