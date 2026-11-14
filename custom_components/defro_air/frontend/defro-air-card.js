/*
 * Karta Defro Air: widok wzorowany na ekranie głównym panelu ST-340 v2.
 *
 * Użycie w dashboardzie:
 *   type: custom:defro-air-card
 *
 * Karta sama znajduje encje integracji defro_air. Opcje:
 *   device_id: <id urządzenia>   # gdy central jest więcej niż jedna
 *   title: <tekst>               # napis zamiast godziny w lewym górnym rogu
 */

const PLATFORM = "defro_air";
const RED = "#e8195a";
const BLUE = "#29abe2";
const PARTY_MIN = 15;
const PARTY_MAX = 720;
const PARTY_STEP = 15;
const HOLIDAY_MAX = 60;
const DAYS = ["Nd.", "Pn.", "Wt.", "Śr.", "Cz.", "Pt.", "Sb."];

const STYLE = `
  :host { display: block; }
  ha-card {
    overflow: hidden;
    color: #fff;
    background: radial-gradient(120% 140% at 75% 60%, #3a3a3a 0%, #232323 55%, #161616 100%);
    font-family: "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  }
  .top {
    display: flex; align-items: center; gap: 14px;
    padding: 10px 16px; background: rgba(0, 0, 0, .45);
  }
  .clock { font-size: 1.05em; letter-spacing: .04em; white-space: nowrap; }
  .icons { display: flex; gap: 10px; flex: 1; flex-wrap: wrap; }
  .icon { opacity: .22; --mdc-icon-size: 22px; display: inline-flex; }
  .icon.on { opacity: 1; }
  .icon.alert.on { color: #ffb300; }
  .icon.fault.on { color: #ff5252; }
  svg { display: block; width: 100%; height: auto; }
  .label { font-size: 34px; font-weight: 600; }
  .temp { font-size: 40px; font-weight: 300; fill: #fff; }
  .flow { font-size: 26px; font-weight: 300; fill: #ddd; }
  .gear { font-size: 36px; font-weight: 300; fill: #fff; }
  .small { font-size: 22px; fill: #ccc; }
  .tag { font-size: 22px; font-weight: 700; letter-spacing: .12em; fill: #ffb300; }
  .bottom { display: flex; flex-wrap: wrap; gap: 8px; padding: 4px 14px 12px; align-items: center; }
  .pill {
    border: 0; border-radius: 999px; padding: 6px 16px; cursor: pointer;
    background: #fff; color: #111; font: inherit; font-size: 1em; white-space: nowrap;
  }
  .pill.on { background: #ffb300; }
  .pill.open { outline: 2px solid ${BLUE}; }
  .pill[disabled] { opacity: .35; cursor: default; }
  .info { margin-left: auto; color: #ccc; font-size: .95em; white-space: nowrap; }
  .editor {
    display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
    padding: 0 14px 14px; color: #ddd;
  }
  .editor button {
    border: 1px solid #777; border-radius: 8px; background: transparent; color: #fff;
    font: inherit; font-size: 1em; padding: 6px 12px; cursor: pointer; min-width: 40px;
  }
  .editor button.go { background: ${BLUE}; border-color: ${BLUE}; color: #000; font-weight: 600; }
  .editor button.stop { background: ${RED}; border-color: ${RED}; font-weight: 600; }
  .editor .value { min-width: 84px; text-align: center; font-size: 1.15em; color: #fff; }
  .missing { padding: 16px; }
`;

const esc = (text) =>
  String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

class DefroAirCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._open = null; // "party" | "holiday" | null
    this._partyMinutes = 30;
    this._holidayDays = 7;
    this._signature = "";
    this.shadowRoot.addEventListener("click", (event) => this._onClick(event));
  }

  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = config || {};
    this._signature = "";
    this._render();
  }

  getCardSize() {
    return 6;
  }

  connectedCallback() {
    // Zegar w nagłówku: odśwież raz na pół minuty.
    this._timer = setInterval(() => this._render(true), 30000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  // --- encje -------------------------------------------------------------

  _entities() {
    const found = {};
    const registry = (this._hass && this._hass.entities) || {};
    let device = this._config.device_id || null;
    for (const entry of Object.values(registry)) {
      if (entry.platform !== PLATFORM || !entry.translation_key) continue;
      if (device === null) device = entry.device_id;
      if (entry.device_id !== device) continue;
      const domain = entry.entity_id.split(".")[0];
      found[`${domain}.${entry.translation_key}`] = entry.entity_id;
    }
    return found;
  }

  _state(key) {
    const id = this._ids[key];
    const state = id ? this._hass.states[id] : undefined;
    if (!state || state.state === "unavailable" || state.state === "unknown") return null;
    return state.state;
  }

  _number(key) {
    const value = this._state(key);
    return value === null || isNaN(Number(value)) ? null : Number(value);
  }

  _on(key) {
    return this._state(key) === "on";
  }

  // --- akcje -------------------------------------------------------------

  _call(domain, service, key, data = {}) {
    const id = this._ids[key];
    if (id) this._hass.callService(domain, service, { entity_id: id, ...data });
  }

  _onClick(event) {
    const target = event.target.closest("[data-action]");
    if (!target || !this._hass) return;
    const action = target.dataset.action;
    const clamp = (value, low, high) => Math.min(high, Math.max(low, value));

    if (action === "toggle-party") this._open = this._open === "party" ? null : "party";
    else if (action === "toggle-holiday") this._open = this._open === "holiday" ? null : "holiday";
    else if (action === "bypass") this._call("switch", "toggle", "switch.bypass_enabled");
    else if (action === "party-minus")
      this._partyMinutes = clamp(this._partyMinutes - PARTY_STEP, PARTY_MIN, PARTY_MAX);
    else if (action === "party-plus")
      this._partyMinutes = clamp(this._partyMinutes + PARTY_STEP, PARTY_MIN, PARTY_MAX);
    else if (action === "party-start") {
      this._call("number", "set_value", "number.party", { value: this._partyMinutes });
      this._open = null;
    } else if (action === "party-stop") {
      this._call("number", "set_value", "number.party", { value: 0 });
      this._open = null;
    } else if (action === "holiday-minus")
      this._holidayDays = clamp(this._holidayDays - 1, 1, HOLIDAY_MAX);
    else if (action === "holiday-plus")
      this._holidayDays = clamp(this._holidayDays + 1, 1, HOLIDAY_MAX);
    else if (action === "holiday-start") {
      this._call("number", "set_value", "number.holiday_days", { value: this._holidayDays });
      this._open = null;
    } else if (action === "holiday-stop") {
      this._call("number", "set_value", "number.holiday_days", { value: 0 });
      this._open = null;
    } else if (action.startsWith("gear-")) {
      const gear = Number(action.slice(5));
      this._call("fan", gear === 0 ? "turn_off" : "set_percentage", "fan.ventilation",
        gear === 0 ? {} : { percentage: Math.round((gear / 3) * 100) });
    }
    this._render(true);
  }

  // --- rysowanie ---------------------------------------------------------

  _render(force = false) {
    if (!this._hass) return;
    this._ids = this._entities();
    if (!Object.keys(this._ids).length) {
      this.shadowRoot.innerHTML = `<style>${STYLE}</style>
        <ha-card><div class="missing">Nie znaleziono encji integracji Defro Air.</div></ha-card>`;
      return;
    }

    const now = new Date();
    const clock = `${DAYS[now.getDay()]} ${String(now.getHours()).padStart(2, "0")}:${String(
      now.getMinutes()
    ).padStart(2, "0")}`;
    const view = {
      clock: this._config.title || clock,
      outdoor: this._number("sensor.outdoor_temperature"),
      extract: this._number("sensor.extract_temperature"),
      supply: this._number("sensor.supply_temperature"),
      exhaust: this._number("sensor.exhaust_temperature"),
      heaterTemp: this._number("sensor.secondary_heating_temperature"),
      supplyFlow: this._number("sensor.supply_flow"),
      extractFlow: this._number("sensor.extract_flow"),
      supplyGear: this._number("sensor.supply_gear"),
      extractGear: this._number("sensor.extract_gear"),
      efficiency: this._number("sensor.efficiency"),
      power: this._number("sensor.recovered_power"),
      bypass: this._on("binary_sensor.bypass_active"),
      bypassEnabled: this._on("switch.bypass_enabled"),
      hasBypassSwitch: Boolean(this._ids["switch.bypass_enabled"]),
      holiday: this._on("binary_sensor.holiday_active"),
      holidayDays: this._number("number.holiday_days"),
      antifreeze: this._on("binary_sensor.antifreeze_active"),
      heater: this._on("binary_sensor.secondary_heating_active"),
      fault: this._on("binary_sensor.problem"),
      party: this._number("number.party"),
      targetGear: this._ids["fan.ventilation"]
        ? this._gearFromFan(this._hass.states[this._ids["fan.ventilation"]])
        : undefined,
      open: this._open,
      partyMinutes: this._partyMinutes,
      holidayDaysInput: this._holidayDays,
    };

    const signature = JSON.stringify(view);
    if (!force && signature === this._signature) return;
    this._signature = signature;

    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <ha-card>
        ${this._top(view)}
        ${this._scene(view)}
        ${this._bottom(view)}
        ${this._editor(view)}
      </ha-card>`;
  }

  _gearFromFan(state) {
    if (!state || state.state === "unavailable") return null;
    if (state.state === "off") return 0;
    const percentage = Number(state.attributes.percentage);
    return isNaN(percentage) ? null : Math.max(1, Math.round((percentage / 100) * 3));
  }

  _top(v) {
    const icon = (name, on, title, extra = "") =>
      `<span class="icon ${extra} ${on ? "on" : ""}" title="${esc(title)}${on ? "" : " (nieaktywne)"}">
         <ha-icon icon="${name}"></ha-icon></span>`;
    return `<div class="top">
      <span class="clock">${esc(v.clock)}</span>
      <span class="icons">
        ${icon("mdi:bag-suitcase", v.holiday, "Urlop")}
        ${icon("mdi:party-popper", (v.party || 0) > 0, "Party")}
        ${icon("mdi:valve", v.bypass, "Bypass otwarty")}
        ${icon("mdi:heating-coil", v.heater, "Grzanie wtórne", "alert")}
        ${icon("mdi:snowflake-alert", v.antifreeze, "Antyzamarzanie (nagrzewnica wstępna)", "alert")}
        ${icon("mdi:alert", v.fault, "Awaria", "fault")}
      </span>
    </div>`;
  }

  _scene(v) {
    const temp = (value) => (value === null ? "–" : `${value.toFixed(1)}°`);
    const flow = (value) => (value === null ? "" : `${Math.round(value)} m³/h`);
    const gear = (value) => (value === null ? "–" : value === 4 ? "min" : String(value));
    const fan = (x, y, spinning) => `
      <g transform="translate(${x} ${y})">
        <circle r="33" fill="none" stroke="#fff" stroke-width="4"/>
        <g>
          ${[0, 90, 180, 270]
            .map((a) => `<ellipse rx="9" ry="13" cx="0" cy="-14" fill="#fff" transform="rotate(${a + 20})"/>`)
            .join("")}
          <circle r="5" fill="#fff"/>
          ${
            spinning
              ? '<animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="2.4s" repeatCount="indefinite"/>'
              : ""
          }
        </g>
      </g>`;
    const head = (x, y, angle, color) =>
      `<polygon points="0,-30 44,0 0,30" fill="${color}" transform="translate(${x} ${y}) rotate(${angle})"/>`;
    const start = (x, y, angle, color) =>
      `<polygon points="0,-20 30,0 0,20" fill="${color}" transform="translate(${x} ${y}) rotate(${angle})"/>`;

    // Praca normalna: oba strumienie stykają się w środku (wymiennik).
    // Bypass: strumień wywiewany omija wymiennik, więc strzałki się rozchodzą.
    const red = v.bypass
      ? "M 430 437 H 415 Q 372 437 372 395 V 300 Q 372 270 352 250 L 340 238"
      : "M 430 437 H 458 Q 500 437 500 395 V 372 Q 500 338 474 314 L 366 226";
    const redHead = v.bypass ? head(326, 224, 225, RED) : head(352, 213, 222, RED);
    const blue = "M 690 187 L 548 316 Q 516 345 516 376 V 395 Q 516 437 558 437 H 588";
    const exchanger = v.bypass
      ? `<text class="tag" x="445" y="350" text-anchor="middle">BYPASS</text>
         <line x1="445" y1="362" x2="445" y2="420" stroke="#ffb300" stroke-width="3" stroke-dasharray="6 6"/>`
      : `<rect x="497" y="360" width="22" height="46" rx="4" fill="#fff" opacity=".85"/>`;

    const heaterRow =
      v.heater || v.heaterTemp !== null
        ? `<g transform="translate(650 438)" stroke="${v.heater ? "#ff7043" : "#777"}" stroke-width="4" fill="none" stroke-linecap="round">
             <path d="M 6 0 q 8 9 0 18 q -8 9 0 18"/><path d="M 20 0 q 8 9 0 18 q -8 9 0 18"/>
             <path d="M 34 0 q 8 9 0 18 q -8 9 0 18"/><path d="M 0 42 H 40"/>
           </g>
           <text class="temp" x="700" y="478">${v.heaterTemp === null ? (v.heater ? "grzanie" : "") : temp(v.heaterTemp)}</text>`
        : "";

    const running = (value) => value !== null && value > 0;
    return `<svg viewBox="0 70 1000 430" role="img" aria-label="Schemat rekuperatora">
      <polygon fill="#9b9b9b" points="430,162 545,96 625,146 625,100 672,100 672,176 812,290 745,290 545,152 478,192"/>
      <polygon fill="#f1f1f1" points="250,362 535,170 700,272 640,272 535,206 305,362"/>
      <rect fill="#f1f1f1" x="275" y="356" width="30" height="110"/>

      <path d="${red}" fill="none" stroke="${RED}" stroke-width="24" stroke-linecap="round" stroke-linejoin="round"/>
      ${redHead}
      ${start(432, 437, 180, RED)}
      <path d="${blue}" fill="none" stroke="${BLUE}" stroke-width="24" stroke-linecap="round" stroke-linejoin="round"/>
      ${head(586, 437, 0, BLUE)}
      ${start(700, 178, 138, BLUE)}
      ${exchanger}

      <text class="label" fill="${RED}" x="50" y="130">Wyrzutnia</text>
      <text class="temp" x="50" y="185">${temp(v.exhaust)}</text>
      ${fan(205, 180, running(v.extractGear))}
      <text class="gear" x="248" y="194">${gear(v.extractGear)}</text>

      <text class="label" fill="${BLUE}" x="755" y="130">Czerpnia</text>
      <text class="temp" x="755" y="185">${temp(v.outdoor)}</text>
      ${fan(884, 180, running(v.supplyGear))}
      <text class="gear" x="926" y="194">${gear(v.supplyGear)}</text>

      <text class="label" fill="${RED}" x="20" y="362">Wywiew</text>
      <text class="temp" x="20" y="416">${temp(v.extract)}</text>
      <text class="flow" x="138" y="416">${flow(v.extractFlow)}</text>

      <text class="label" fill="${BLUE}" x="695" y="362">Nawiew</text>
      <text class="temp" x="695" y="416">${temp(v.supply)}</text>
      <text class="flow" x="815" y="416">${flow(v.supplyFlow)}</text>
      ${heaterRow}
    </svg>`;
  }

  _bottom(v) {
    const partyOn = (v.party || 0) > 0;
    const hhmm = (minutes) =>
      `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
    const pill = (action, text, on, open = false, disabled = false) =>
      `<button class="pill ${on ? "on" : ""} ${open ? "open" : ""}" data-action="${action}" ${
        disabled ? "disabled" : ""
      }>${esc(text)}</button>`;

    const info = [];
    if (v.efficiency !== null) info.push(`sprawność ${Math.round(v.efficiency)}%`);
    if (v.power !== null) info.push(`${Math.round(v.power)} W`);

    const gears =
      v.targetGear === undefined
        ? ""
        : [0, 1, 2, 3].map((g) => pill(`gear-${g}`, g === 0 ? "stop" : `bieg ${g}`, v.targetGear === g)).join("");

    return `<div class="bottom">
      ${pill("toggle-party", `party ${hhmm(partyOn ? v.party : 0)}`, partyOn, v.open === "party", v.party === null)}
      ${
        v.hasBypassSwitch
          ? pill("bypass", `bypass ${v.bypassEnabled ? "wł." : "wył."}`, v.bypassEnabled)
          : ""
      }
      ${pill(
        "toggle-holiday",
        v.holiday || (v.holidayDays || 0) > 0 ? `urlop ${v.holidayDays || ""} d` : "urlop",
        v.holiday || (v.holidayDays || 0) > 0,
        v.open === "holiday",
        v.holidayDays === null
      )}
      ${gears}
      <span class="info">${esc(info.join(" · "))}</span>
    </div>`;
  }

  _editor(v) {
    if (v.open === "party") {
      const active = (v.party || 0) > 0;
      return `<div class="editor">
        <span>Czas party:</span>
        <button data-action="party-minus">−</button>
        <span class="value">${v.partyMinutes} min</span>
        <button data-action="party-plus">+</button>
        <button class="go" data-action="party-start">${active ? "Ustaw" : "Start"}</button>
        ${active ? '<button class="stop" data-action="party-stop">Zakończ party</button>' : ""}
      </div>`;
    }
    if (v.open === "holiday") {
      const active = v.holiday || (v.holidayDays || 0) > 0;
      return `<div class="editor">
        <span>Urlop:</span>
        <button data-action="holiday-minus">−</button>
        <span class="value">${v.holidayDaysInput} d</span>
        <button data-action="holiday-plus">+</button>
        <button class="go" data-action="holiday-start">${active ? "Ustaw" : "Start"}</button>
        ${active ? '<button class="stop" data-action="holiday-stop">Zakończ urlop</button>' : ""}
      </div>`;
    }
    return "";
  }
}

if (!customElements.get("defro-air-card")) {
  customElements.define("defro-air-card", DefroAirCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "defro-air-card",
    name: "Defro Air",
    description: "Widok rekuperatora wzorowany na panelu ST-340 v2, ze sterowaniem.",
  });
}
