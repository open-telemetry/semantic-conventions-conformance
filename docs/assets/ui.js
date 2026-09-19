// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { LEVELS, LEVEL_LABEL, levelColor } from "./data.js";

/**
 * Build an element, treating string content as text.
 *
 * @param {string} tag the element name
 * @param {Object<string,*>} [attrs] attributes, plus `text` for text content
 *   and `on*` for event handlers; null, undefined and false are skipped
 * @param {(Node|string|null|false)[]|Node|string} [children] appended in order,
 *   flattened, with nullish and false entries skipped
 * @returns {HTMLElement}
 */
export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "text") node.textContent = String(value);
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of [children].flat(3)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(
      child instanceof Node ? child : document.createTextNode(String(child)),
    );
  }
  return node;
}

/**
 * @param {string[]} [levels] the requirement levels to show, in order
 * @returns {HTMLElement} a `<p>` with one swatch and label per level
 */
export function levelLegend(levels = LEVELS) {
  return el(
    "p",
    { class: "legend" },
    levels.map((level) =>
      el("span", {}, [
        el("i", { style: `background:${levelColor(level)}` }),
        LEVEL_LABEL[level] ?? level,
      ]),
    ),
  );
}

/** Distinct ids, so a label and the thing it names can find each other. */
let sequence = 0;
const uid = (prefix) => `${prefix}-${(sequence += 1)}`;

const APPLE = () => {
  const ua = globalThis.navigator?.userAgent ?? "";
  return /Mac|iP(hone|ad|od)/.test(ua);
};

/**
 * One item of a {@link palette}.
 *
 * @typedef {object} PaletteItem
 * @property {string} value what {@link palette}'s `onPick` is called with
 * @property {string} name the item's own label
 * @property {string} group the heading it sits under; items are shown in the
 *   order given, so equal groups have to be adjacent
 * @property {string} [badge] a short kind, shown before the name
 * @property {number} [count] shown right-aligned, as a size
 */

/**
 * A searchable list of routes behind one button.
 *
 * Navigation, unlike a filter, changes what the page is about, so it reads as
 * one prominent control rather than as another select — and a select cannot
 * be searched, which matters once there are more entries than fit on screen.
 *
 * @param {object} options
 * @param {string} options.label what is being chosen, e.g. `Signal`
 * @param {PaletteItem[]} options.items every choice, grouped and in order
 * @param {string} options.value the current choice's `value`
 * @param {(value: string) => void} options.onPick called with a new choice;
 *   picking the current one just closes the panel
 * @returns {{node: HTMLElement}}
 */
export function palette({ label, items, value, onPick }) {
  const listId = uid("palette");
  const chosen = items.find((item) => item.value === value);
  const lower = label.toLowerCase();

  const button = el(
    "button",
    {
      type: "button",
      class: "picker",
      "aria-haspopup": "listbox",
      "aria-expanded": "false",
      onclick: () => open(panel.hidden),
    },
    [
      el("span", { class: "picker-what", text: label }),
      chosen?.badge && el("span", { class: "badge", text: chosen.badge }),
      el("span", {
        class: "picker-name mono",
        text: chosen ? chosen.name : `Choose a ${lower}…`,
      }),
      el("kbd", { class: "picker-key", text: APPLE() ? "⌘K" : "Ctrl K" }),
    ],
  );

  const query = el("input", {
    type: "search",
    class: "palette-query",
    role: "combobox",
    "aria-expanded": "true",
    "aria-controls": listId,
    "aria-autocomplete": "list",
    "aria-label": `Search ${lower}s`,
    placeholder: `Search ${items.length} ${lower}s…`,
    oninput: () => draw(),
    onkeydown: (event) => keys(event),
  });
  const list = el("div", {
    id: listId,
    class: "palette-list",
    role: "listbox",
    "aria-label": label,
  });
  const panel = el(
    "div",
    {
      class: "palette",
      role: "dialog",
      "aria-modal": "true",
      "aria-label": `Choose a ${lower}`,
      hidden: true,
    },
    [query, list],
  );
  const veil = el("div", {
    class: "veil",
    hidden: true,
    onclick: () => open(false),
  });

  /** The items matching the query, in the order they are drawn. */
  let shown = items;
  let active = Math.max(
    items.findIndex((item) => item.value === value),
    0,
  );

  const haystack = (item) =>
    `${item.badge ?? ""} ${item.name} ${item.group}`.toLowerCase();

  function option(item, index) {
    return el(
      "div",
      {
        class: "palette-option",
        id: `${listId}-o${index}`,
        role: "option",
        "aria-selected": item.value === value ? "true" : "false",
        onclick: () => pick(item),
        onmousemove: () => {
          if (active === index) return;
          active = index;
          mark();
        },
      },
      [
        item.badge && el("span", { class: "badge", text: item.badge }),
        el("span", { class: "palette-name mono", text: item.name }),
        item.count !== undefined &&
          el("span", { class: "palette-count", text: String(item.count) }),
      ],
    );
  }

  function draw() {
    const text = query.value.trim().toLowerCase();
    const before = shown;
    shown = text
      ? items.filter((item) => haystack(item).includes(text))
      : items;
    // A new set of results starts at the current choice, or at the top if that
    // is not among them. Keeping the old offset leaves the highlight — and the
    // scroll — wherever the longer list happened to end.
    if (
      shown.length !== before.length ||
      shown.some((it, i) => it !== before[i])
    ) {
      active = Math.max(
        shown.findIndex((item) => item.value === value),
        0,
      );
    }

    // Group headings have to wrap their options, not merely precede them, or a
    // screen reader reads 34 names with nothing saying which domain each is in.
    const groups = [];
    shown.forEach((item, index) => {
      const last = groups.at(-1);
      const node = option(item, index);
      if (last && last.name === item.group) last.options.push(node);
      else groups.push({ name: item.group, options: [node] });
    });

    list.replaceChildren(
      ...(groups.length
        ? groups.map((group) =>
            el("div", { role: "group", "aria-label": group.name }, [
              el("p", { class: "palette-group", text: group.name }),
              ...group.options,
            ]),
          )
        : [
            el("p", {
              class: "palette-none",
              text: `No ${lower} matches “${query.value.trim()}”.`,
            }),
          ]),
    );
    mark();
  }

  function mark() {
    const options = [...list.querySelectorAll('[role="option"]')];
    options.forEach((option, index) => {
      if (index === active) option.setAttribute("data-active", "");
      else option.removeAttribute("data-active");
    });
    const current = options[active];
    query.setAttribute("aria-activedescendant", current?.id ?? "");
    // Scrolling the first option into view pushes its group heading out of it.
    if (active === 0) list.scrollTop = 0;
    else current?.scrollIntoView?.({ block: "nearest" });
  }

  function keys(event) {
    const step = { ArrowDown: 1, ArrowUp: -1 }[event.key];
    if (step && shown.length) {
      event.preventDefault();
      active = (active + step + shown.length) % shown.length;
      mark();
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      active = event.key === "Home" ? 0 : shown.length - 1;
      mark();
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (shown[active]) pick(shown[active]);
    } else if (event.key === "Escape") {
      event.preventDefault();
      open(false);
    }
  }

  function pick(item) {
    open(false);
    if (item.value !== value) onPick(item.value);
  }

  function open(next = true) {
    panel.hidden = !next;
    veil.hidden = !next;
    button.setAttribute("aria-expanded", String(next));
    if (!next) {
      button.focus();
      return;
    }
    query.value = "";
    active = Math.max(
      items.findIndex((item) => item.value === value),
      0,
    );
    draw();
    query.focus();
  }

  // The view is replaced wholesale on every route change, so the handler has to
  // outlive nothing: it retires itself once its own button is off the document.
  const hotkey = (event) => {
    if (!button.isConnected) {
      document.removeEventListener("keydown", hotkey);
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key?.toLowerCase() === "k") {
      event.preventDefault();
      open(panel.hidden);
    }
  };
  document.addEventListener("keydown", hotkey);

  draw();
  return { node: el("div", { class: "picker-wrap" }, [button, veil, panel]) };
}

const optionOf = (raw) =>
  typeof raw === "string" ? { value: raw, label: raw } : raw;
const labelOf = (options, value) =>
  options.map(optionOf).find((option) => option.value === value)?.label ??
  value;

/**
 * A search box and a row of filters, with every active one shown as a chip.
 *
 * Filters that are off are the common case, so they cost one line; what is on
 * is spelled out below it, because a control that looks the same whether or
 * not it is doing something is the reason a view surprises you.
 *
 * @param {object} options
 * @param {string} options.search placeholder for the search box
 * @param {{key: string, label: string, options: (string|{value: string,
 *   label: string, count?: number, color?: string})[]}[]} [options.pills]
 *   toggle groups, any number of them on at once
 * @param {{key: string, label: string,
 *   options: {value: string, label: string}[]}[]} [options.segments] exclusive
 *   choices; the first option is the default and never shows as a chip
 * @param {{key: string, label: string, all: string,
 *   options: (string|{value: string, label: string})[]}[]} [options.selects]
 *   long lists, folded away until asked for
 * @param {Object<string,string|string[]>} [options.state] the starting state,
 *   as {@link filterBar} reports it; values not on offer are dropped
 * @param {(state: Object<string,string|string[]>) => string|undefined}
 *   options.onChange called with `{q, ...keys}` on every change; its return
 *   value is shown as the result count
 * @returns {{node: HTMLElement}}
 */
export function filterBar({
  search,
  pills = [],
  segments = [],
  selects = [],
  state: initial = {},
  onChange,
}) {
  // A starting state can come from a link, so none of it can be trusted to be
  // on offer: a stale `?lang=` would otherwise filter every column away.
  const state = {
    q: String(initial.q ?? "")
      .trim()
      .toLowerCase(),
  };
  for (const pill of pills) {
    const offered = new Set(pill.options.map((raw) => optionOf(raw).value));
    state[pill.key] = [...new Set(initial[pill.key] ?? [])].filter((value) =>
      offered.has(value),
    );
  }
  for (const segment of segments) {
    const offered = segment.options.map((option) => option.value);
    state[segment.key] = offered.includes(initial[segment.key])
      ? initial[segment.key]
      : offered[0];
  }
  for (const select of selects) {
    const offered = select.options.map((raw) => optionOf(raw).value);
    state[select.key] = offered.includes(initial[select.key])
      ? initial[select.key]
      : "";
  }

  const snapshot = () =>
    Object.fromEntries(
      Object.entries(state).map(([key, value]) => [
        key,
        Array.isArray(value) ? [...value] : value,
      ]),
    );

  const count = el("span", { class: "count", role: "status" });
  const chips = el("div", { class: "chips", hidden: true });
  /** Written back to the controls after any change, wherever it came from. */
  const syncers = [];

  const input = el("input", {
    type: "search",
    class: "search",
    placeholder: search ?? "Search…",
    "aria-label": search ?? "Search",
    value: state.q,
    oninput: (event) => {
      state.q = event.target.value.trim().toLowerCase();
      apply();
    },
  });

  const pillGroups = pills.map((pill) => {
    const nodes = pill.options.map(optionOf).map((option) => {
      const node = el(
        "button",
        {
          type: "button",
          class: "pill",
          "aria-pressed": "false",
          style: option.color ? `--pill:${option.color}` : null,
          onclick: () => {
            const on = state[pill.key].includes(option.value);
            state[pill.key] = on
              ? state[pill.key].filter((value) => value !== option.value)
              : [...state[pill.key], option.value];
            apply();
          },
        },
        [
          option.label,
          option.count !== undefined &&
            el("span", { class: "pill-count", text: String(option.count) }),
        ],
      );
      return { node, value: option.value };
    });
    syncers.push(() => {
      for (const { node, value } of nodes) {
        node.setAttribute(
          "aria-pressed",
          String(state[pill.key].includes(value)),
        );
      }
    });
    return el(
      "div",
      { class: "pills", role: "group", "aria-label": pill.label },
      nodes.map(({ node }) => node),
    );
  });

  const segmentGroups = segments.map((segment) => {
    const nodes = segment.options.map((option) => {
      const node = el("button", {
        type: "button",
        class: "segment",
        role: "radio",
        "aria-checked": "false",
        text: option.label,
        onclick: () => {
          state[segment.key] = option.value;
          apply();
        },
      });
      return { node, value: option.value };
    });
    syncers.push(() => {
      for (const { node, value } of nodes) {
        node.setAttribute("aria-checked", String(state[segment.key] === value));
      }
    });
    return el(
      "div",
      { class: "segments", role: "radiogroup", "aria-label": segment.label },
      nodes.map(({ node }) => node),
    );
  });

  const selectRows = selects.map((select) => {
    const node = el(
      "select",
      {
        "aria-label": select.label,
        onchange: (event) => {
          state[select.key] = event.target.value;
          apply();
        },
      },
      [
        el("option", { value: "", text: select.all ?? "All" }),
        ...select.options
          .map(optionOf)
          .map((option) =>
            el("option", { value: option.value, text: option.label }),
          ),
      ],
    );
    syncers.push(() => {
      node.value = state[select.key];
    });
    return el("label", { class: "more-row" }, [
      el("span", { text: select.label }),
      node,
    ]);
  });

  const drawer = el("div", { class: "more-drawer", hidden: true }, selectRows);
  const disclosure = el("button", {
    type: "button",
    class: "more",
    "aria-expanded": "false",
    text: "More filters",
    onclick: () => {
      drawer.hidden = !drawer.hidden;
      disclosure.setAttribute("aria-expanded", String(!drawer.hidden));
    },
  });
  // A link that arrives with one of these set has to show what it set.
  if (selects.some((select) => state[select.key])) {
    drawer.hidden = false;
    disclosure.setAttribute("aria-expanded", "true");
  }

  function active() {
    const found = [];
    if (state.q) {
      found.push({
        label: `“${state.q}”`,
        clear: () => {
          state.q = "";
          input.value = "";
        },
      });
    }
    // In the order the pills are drawn, not the order they were clicked, so
    // that turning one on does not shuffle the ones already there.
    for (const pill of pills) {
      for (const option of pill.options.map(optionOf)) {
        if (!state[pill.key].includes(option.value)) continue;
        found.push({
          label: option.label,
          color: option.color,
          clear: () => {
            state[pill.key] = state[pill.key].filter(
              (value) => value !== option.value,
            );
          },
        });
      }
    }
    for (const segment of segments) {
      if (state[segment.key] === segment.options[0].value) continue;
      found.push({
        label: labelOf(segment.options, state[segment.key]),
        clear: () => {
          state[segment.key] = segment.options[0].value;
        },
      });
    }
    for (const select of selects) {
      if (!state[select.key]) continue;
      found.push({
        label: labelOf(select.options, state[select.key]),
        clear: () => {
          state[select.key] = "";
        },
      });
    }
    return found;
  }

  function apply() {
    const found = active();
    chips.hidden = !found.length;
    chips.replaceChildren(
      ...(found.length
        ? [
            el("span", { class: "chips-what", text: "Filtered by" }),
            ...found.map((chip) =>
              el("button", {
                type: "button",
                class: "chip",
                style: chip.color ? `--pill:${chip.color}` : null,
                "aria-label": `Remove filter ${chip.label}`,
                text: `${chip.label} ✕`,
                onclick: () => {
                  chip.clear();
                  apply();
                },
              }),
            ),
            el("button", {
              type: "button",
              class: "chip chip-clear",
              text: "Clear all",
              onclick: () => {
                for (const chip of active()) chip.clear();
                apply();
              },
            }),
          ]
        : []),
    );
    for (const sync of syncers) sync();
    count.textContent = onChange(snapshot()) ?? "";
  }

  // `/` is where a search box lives on every site that has one.
  const hotkey = (event) => {
    if (!input.isConnected) {
      document.removeEventListener("keydown", hotkey);
      return;
    }
    const target = event.target;
    const typing = target?.tagName === "INPUT" || target?.tagName === "SELECT";
    if (event.key === "/" && !typing) {
      event.preventDefault();
      input.focus();
    }
  };
  document.addEventListener("keydown", hotkey);

  const node = el("div", { class: "filterbar" }, [
    el("div", { class: "filterbar-row" }, [
      input,
      ...pillGroups,
      ...segmentGroups,
      selectRows.length && disclosure,
      count,
    ]),
    selectRows.length && drawer,
    chips,
  ]);
  apply();
  return { node };
}
