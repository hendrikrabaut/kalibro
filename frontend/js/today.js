import { api } from "./api.js";
import { card, h } from "./dom.js";
import { STATUS_TEXT, dateTime, duration, localDateKey, time } from "./format.js";
import { getTimer, startTask, timerCard } from "./timer.js";
import { route } from "./main.js";

export async function renderToday() {
  const [timer, plan] = await Promise.all([getTimer(), api("/api/plan")]);
  const timerView = timerCard(timer, route);

  const today = localDateKey(new Date().toISOString());
  const now = Date.now();
  const todays = plan.blocks.filter((b) => localDateKey(b.start_at) === today && !b.done);
  const next = plan.blocks.find((b) => new Date(b.end_at) > now && !b.done);

  const blocks = todays.length
    ? todays.map((block) => h("div", { class: `block${new Date(block.end_at) < now ? " past" : ""}` },
        h("span", { class: "when" }, `${time(block.start_at)}–${time(block.end_at)}`),
        h("span", { style: "flex:1" }, block.title),
        timer.running && timer.task.id === block.task_id
          ? h("span", { class: "badge ok" }, "loopt")
          : h("button", { class: "primary", onclick: async () => { await startTask(block.task_id); route(); } }, "Start"),
      ))
    : [h("p", { class: "muted" }, next ? `Vandaag niets gepland. Volgende blok: ${dateTime(next.start_at)}, ${next.title}.` : "Niets gepland. Maak een plan op de pagina Plan.")];

  const warnings = [];
  if (!plan.version) warnings.push(h("p", {}, "Nog geen plan. ", h("a", { href: "#plan" }, "Maak er een")));
  if (plan.late_tasks.length) warnings.push(h("p", {}, h("span", { class: "badge bad" }, `${plan.late_tasks.length} taken`), " halen hun deadline niet met de huidige planning. ", h("a", { href: "#plan" }, "Herplan")));
  if (plan.needs_estimate.length) warnings.push(h("p", {}, h("span", { class: "badge tight" }, `${plan.needs_estimate.length} taken`), " uit gescande PDF's hebben een eigen schatting nodig."));

  const deadlines = plan.deadlines.slice(0, 6).map((d) => h("tr", {},
    h("td", {}, d.title),
    h("td", { class: "num" }, dateTime(d.due_at)),
    h("td", { class: "right num" }, `${duration(d.work_s)} / ${duration(d.capacity_s)}`),
    h("td", {}, h("span", { class: `badge ${d.status}` }, STATUS_TEXT[d.status])),
  ));

  return {
    nodes: [
      timerView.node,
      warnings.length ? card(null, ...warnings) : null,
      card("Vandaag", h("div", { class: "day" }, ...blocks)),
      card("Komende deadlines",
        deadlines.length
          ? h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Deadline"), h("th", {}, "Wanneer"), h("th", { class: "right" }, "Werk / tijd"), h("th", {}, "Status"))), h("tbody", {}, ...deadlines)))
          : h("p", { class: "muted" }, "Geen deadlines met taken eraan gekoppeld.")),
    ].filter(Boolean),
    cleanup: timerView.stop,
  };
}
