import { api } from "./api.js";
import { attempt, card, h } from "./dom.js";
import { STATUS_TEXT, dateTime, day, duration, localDateKey, time } from "./format.js";
import { route } from "./main.js";

const SHOWN_DAYS = 21;

export async function renderPlan() {
  const [plan, courses] = await Promise.all([api("/api/plan"), api("/api/courses")]);
  const courseNames = Object.fromEntries(courses.map((c) => [c.id, c.name]));

  const reason = h("input", { placeholder: "Reden (optioneel), bv. achter op schema", style: "flex:1;min-width:14em" });
  const replan = h("form", { class: "row", onsubmit: async (event) => {
    event.preventDefault();
    const result = await attempt(() => api("/api/plan", { json: { reason: reason.value || null } }), "Nieuw plan gemaakt");
    if (result) route();
  } }, reason, h("button", { class: "primary" }, plan.version ? "Herplan vanaf nu" : "Maak een plan"));

  const feedUrl = new URL("/api/calendar.ics", location.href).href;
  const header = card(null,
    h("div", { class: "row spread" },
      h("div", {},
        h("h1", {}, "Plan"),
        plan.version
          ? h("p", { class: "muted small" }, `Versie ${plan.version.id} van ${dateTime(plan.version.created_at)}${plan.version.reason ? ` · ${plan.version.reason}` : ""}`)
          : h("p", { class: "muted small" }, "Nog geen plan.")),
      h("div", { class: "small" },
        h("div", {}, `Nog te doen: ${duration(plan.work_s)}`),
        h("div", { class: "muted" }, `Vrije tijd tot ${dateTime(plan.horizon)}: ${duration(plan.free_s)}`))),
    replan,
    h("p", { class: "muted small" }, "Herplannen verdeelt al het resterende werk (schatting min gelogde tijd) opnieuw vanaf nu. Oude versies blijven bewaard."),
    h("p", { class: "small" }, "Agenda: abonneer je op ", h("a", { href: feedUrl }, feedUrl),
      h("span", { class: "muted" }, " (in Google Agenda: Andere agenda's → Via URL; werkt enkel als je agenda de server kan bereiken), of download het bestand eenmalig.")),
  );

  const feasibility = plan.deadlines.map((d) => h("tr", {},
    h("td", {}, d.title, h("div", { class: "muted small" }, courseNames[d.course_id] || "")),
    h("td", { class: "num" }, dateTime(d.due_at)),
    h("td", { class: "right num" }, duration(d.work_s), h("div", { class: "muted small" }, `tot ${duration(d.work_high_s)} als het tegenvalt`)),
    h("td", { class: "right num" }, duration(d.capacity_s)),
    h("td", {}, h("span", { class: `badge ${d.status}` }, STATUS_TEXT[d.status])),
  ));

  const problems = [];
  if (plan.late_tasks.length) problems.push(h("p", {}, h("b", {}, "Te laat: "), plan.late_tasks.map((t) => t.title).join(", ")));
  if (plan.unscheduled.length) problems.push(h("p", {}, h("b", {}, "Past niet meer in de vrije tijd: "), plan.unscheduled.map((t) => `${t.title} (${duration(t.remaining_s)})`).join(", ")));
  if (plan.needs_estimate.length) problems.push(h("p", {}, h("b", {}, "Niet ingepland, eerst zelf schatten: "), plan.needs_estimate.map((t) => t.title).join(", ")));

  // Blocks per local day, from today on.
  const today = localDateKey(new Date().toISOString());
  const byDay = new Map();
  for (const block of plan.blocks) {
    const key = localDateKey(block.start_at);
    if (key < today) continue;
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key).push(block);
  }
  const now = Date.now();
  const days = [...byDay.entries()].slice(0, SHOWN_DAYS).map(([, blocks]) => h("div", { class: "day" },
    h("h3", {}, day(blocks[0].start_at), h("span", { class: "muted small" }, ` · ${duration(blocks.reduce((s, b) => s + (new Date(b.end_at) - new Date(b.start_at)) / 1000, 0))}`)),
    ...blocks.map((b) => h("div", { class: `block${b.done || new Date(b.end_at) < now ? " past" : ""}` },
      h("span", { class: "when" }, `${time(b.start_at)}–${time(b.end_at)}`),
      h("span", {}, b.title, h("span", { class: "muted small" }, ` · ${courseNames[b.course_id] || ""}${b.done ? " · af" : ""}`)))),
  ));

  return [
    header,
    problems.length ? card("Let op", ...problems) : null,
    card("Haalbaarheid per deadline",
      feasibility.length
        ? h("div", { class: "table-wrap" }, h("table", {},
            h("thead", {}, h("tr", {}, h("th", {}, "Deadline"), h("th", {}, "Wanneer"), h("th", { class: "right" }, "Werk tot dan"), h("th", { class: "right" }, "Vrije tijd"), h("th", {}, "Status"))),
            h("tbody", {}, ...feasibility)))
        : h("p", { class: "muted" }, "Koppel taken aan een deadline om te zien of het haalbaar is."),
      h("p", { class: "muted small" }, "Werk telt ook alle taken met een eerdere deadline mee. ‘Tegenvalt’ is de bovengrens van de marge.")),
    card(`Komende ${SHOWN_DAYS} dagen`, days.length ? h("div", { class: "day" }, ...days) : h("p", { class: "muted" }, plan.version ? "Geen blokken. Is er beschikbaarheid ingesteld?" : "Maak eerst een plan.")),
  ].filter(Boolean);
}
