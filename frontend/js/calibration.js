import { api } from "./api.js";
import { attempt, card, h, svg } from "./dom.js";
import { typeLabel } from "./format.js";

const PER_UNIT = { page: "pagina", slide: "slide", exercise: "vraag", item: "stuk" };
import { route } from "./main.js";

function accuracyChart(weeks) {
  const width = 640, height = 200, pad = 28;
  const max = Math.max(50, ...weeks.map((w) => w.mape));
  const step = (width - pad * 2) / weeks.length;
  const chart = svg("svg", { class: "chart", viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "Afwijking per week" });
  chart.append(svg("line", { class: "axis", x1: pad, x2: width - pad, y1: height - pad, y2: height - pad }));
  weeks.forEach((week, index) => {
    const barHeight = (week.mape / max) * (height - pad * 2);
    const x = pad + index * step + step * 0.15;
    const bar = svg("rect", { class: "bar", x, y: height - pad - barHeight, width: step * 0.7, height: barHeight, rx: 3, opacity: week.live ? 0.5 : 1 });
    const title = svg("title");
    title.textContent = `week van ${week.week_start}: ${week.mape}% over ${week.task_count} taken${week.live ? " (lopend)" : ""}`;
    bar.append(title);
    const value = svg("text", { x: x + step * 0.35, y: height - pad - barHeight - 4, "text-anchor": "middle" });
    value.textContent = `${Math.round(week.mape)}%`;
    const label = svg("text", { x: x + step * 0.35, y: height - pad + 14, "text-anchor": "middle" });
    label.textContent = week.week_start.slice(5);
    chart.append(bar, value, label);
  });
  return chart;
}

export async function renderCalibration() {
  const [calibration, weeks, rates] = await Promise.all([api("/api/calibration"), api("/api/calibration/accuracy"), api("/api/rates")]);

  const rateRows = rates.map((rate) => {
    const input = h("input", { type: "number", min: "0.1", step: "any", value: Math.round(rate.seconds_per_unit / 6) / 10, style: "width:6em" });
    return h("tr", {},
      h("td", {}, typeLabel(rate.task_type)),
      h("td", { class: "nowrap" }, input, ` min per ${PER_UNIT[rate.unit] || rate.unit}`),
      h("td", { class: "right num" }, calibration.type_factors[rate.task_type] ? `× ${calibration.type_factors[rate.task_type]}` : h("span", { class: "muted", title: "nog geen afgeronde taken van dit type" }, "–")),
      h("td", { class: "right" }, h("button", { onclick: async () => {
        const seconds = Number(input.value) * 60;
        if (await attempt(() => api(`/api/rates/${rate.task_type}`, { method: "PUT", json: { unit: rate.unit, seconds_per_unit: seconds } }), "Tempo opgeslagen")) route();
      } }, "Opslaan")));
  });

  const factorRows = calibration.factors.map((row) => h("tr", {},
    h("td", {}, row.course), h("td", {}, typeLabel(row.task_type)),
    h("td", { class: "right num" }, `× ${row.factor}`),
    h("td", { class: "right num muted" }, `${row.sample_size} taken`)));

  return [
    h("h1", {}, "Kalibratie"),
    card("Afwijking per week (MAPE)",
      weeks.length ? accuracyChart(weeks) : h("p", { class: "muted" }, "Nog geen afgeronde taken met gelogde tijd."),
      h("p", { class: "muted small" }, "Hoeveel de schatting gemiddeld afwijkt van je echte tijd, gemeten tegen de schatting zoals ze was toen je begon. Lager is beter."),
    ),
    h("div", { class: "grid-2" },
      card("Basistempo",
        h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Type"), h("th", {}, "Tempo"), h("th", { class: "right" }, "Geleerd"), h("th", {}))), h("tbody", {}, ...rateRows))),
        h("p", { class: "muted small" }, "De kalibratie werkt bovenop dit tempo. Pas het alleen aan als het er duidelijk naast zit.")),
      card("Correctiefactoren",
        h("p", { class: "small" }, `${calibration.finished_tasks} afgeronde taken · algemeen × ${calibration.global_factor}`),
        factorRows.length ? h("div", { class: "table-wrap" }, h("table", {}, h("tbody", {}, ...factorRows))) : null,
        h("p", { class: "muted small" }, `Met weinig data wordt een factor naar het gemiddelde getrokken: elk niveau telt als ${calibration.prior_weight} taken. Spreiding (log): ${calibration.sigma}; die bepaalt de marge.`)),
    ),
  ];
}
