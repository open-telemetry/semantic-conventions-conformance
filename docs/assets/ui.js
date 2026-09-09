// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// The pieces every view draws with. Hand-rolled because every visualization
// here is a table or a grid of cells, which is not worth a charting dependency.

import { LEVELS, LEVEL_LABEL, levelColor } from './data.js';

/**
 * Build an element. There is no `html` escape hatch on purpose: nest a child
 * element instead.
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
    if (key === 'text') node.textContent = String(value);
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : String(value));
  }
  for (const child of [children].flat(3)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

/**
 * @param {string[]} [levels] the requirement levels to show, in order
 * @returns {HTMLElement} a `<p>` with one swatch and label per level
 */
export function levelLegend(levels = LEVELS) {
  return el(
    'p',
    { class: 'legend' },
    levels.map((level) =>
      el('span', {}, [
        el('i', { style: `background:${levelColor(level)}` }),
        LEVEL_LABEL[level] ?? level,
      ]),
    ),
  );
}

/**
 * A search box plus select filters, calling back on any change.
 *
 * @param {object} options
 * @param {string} options.search placeholder for the search box
 * @param {{key: string, label: string, all: string|null, value?: string,
 *   options: (string|{value: string, label: string})[]}[]} [options.filters]
 *   one select each. `all` is the label of the no-filter choice, or null where
 *   the view below cannot do without a choice; `value` is the starting one.
 * @param {(state: Object<string,string>) => string|undefined} options.onChange
 *   called with `{q, ...filterKeys}` on every change; its return value is shown
 *   as the result count
 * @returns {HTMLElement}
 */
export function toolbar({ search, filters = [], onChange }) {
  const state = {
    q: '',
    ...Object.fromEntries(filters.map((f) => [f.key, f.value ?? ''])),
  };
  const count = el('span', { class: 'count' });

  const emit = () => {
    count.textContent = onChange({ ...state }) ?? '';
  };

  const input = el('input', {
    type: 'search',
    placeholder: search ?? 'Search…',
    'aria-label': search ?? 'Search',
    oninput: (event) => {
      state.q = event.target.value.trim().toLowerCase();
      emit();
    },
  });

  const controls = filters.map((filter) => {
    const select = el(
      'select',
      {
        'aria-label': filter.label,
        onchange: (event) => {
          state[filter.key] = event.target.value;
          emit();
        },
      },
      [
        filter.all === null
          ? null
          : el('option', { value: '', text: filter.all ?? 'All' }),
        ...filter.options.map((option) =>
          el('option', {
            value: option.value ?? option,
            text: option.label ?? option,
          }),
        ),
      ],
    );
    // Start the control and `state` in agreement: an unmatched `value` falls
    // back to the first option.
    select.value = state[filter.key];
    if (select.selectedIndex < 0) select.selectedIndex = 0;
    state[filter.key] = select.value;
    // The name in its own element so every select can start at one column.
    return el('label', {}, [el('span', { text: filter.label }), select]);
  });

  // One control per line: there are enough of them now that a single wrapping
  // row reflowed into an unreadable shape at most widths.
  const node = el('div', { class: 'toolbar' }, [
    el('div', { class: 'toolbar-row' }, [input, count]),
    ...controls,
  ]);
  emit();
  return { node, state };
}
