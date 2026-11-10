import { api } from "./api.js";
import { attempt, card, fields, h } from "./dom.js";
import { WEEKDAYS, duration } from "./format.js";
import { route } from "./main.js";

const minutes = (clock) => { const [hh, mm] = clock.split(":").map(Number); return hh * 60 + mm; };

export async function renderAvailability() {
  const [slots, exceptions] = await Promise.all([api("/api/availability/slots"), api("/api/availability/exceptions")]);
  const weekly = slots.reduce((sum, s) => sum + minutes(s.end_time) - minutes(s.start_time), 0) * 60;

  const slotForm = h("form", { class: "inline", onsubmit: async (event) => {
    event.preventDefault();
    const data = fields(event.target);
    const days = data.weekday === "werkdagen" ? [0, 1, 2, 3, 4] : data.weekday === "weekend" ? [5, 6] : [Number(data.weekday)];
    for (const weekday of days) {
      const ok = await attempt(() => api("/api/availability/slots", { json: { weekday, start_time: data.start_time, end_time: data.end_time } }));
      if (!ok) return;
    }
    route();
  } },
    h("label", {}, "Dag", h("select", { name: "weekday" },
      h("option", { value: "werkdagen" }, "elke werkdag"), h("option", { value: "weekend" }, "zaterdag en zondag"),
      ...WEEKDAYS.map((name, index) => h("option", { value: index }, name)))),
    h("label", {}, "Van", h("input", { name: "start_time", type: "time", required: true, value: "19:00" })),
    h("label", {}, "Tot", h("input", { name: "end_time", type: "time", required: true, value: "21:00" })),
    h("button", { class: "primary" }, "Toevoegen"),
  );

  const week = WEEKDAYS.map((name, index) => {
    const todays = slots.filter((s) => s.weekday === index);
    return h("tr", {},
      h("td", {}, name),
      h("td", {}, todays.length ? todays.map((s) => h("span", { class: "badge", style: "margin-right:6px" },
        `${s.start_time}–${s.end_time} `,
        h("button", { class: "link danger", title: "Verwijderen", onclick: async () => { if (await attempt(() => api(`/api/availability/slots/${s.id}`, { method: "DELETE" }))) route(); } }, "×"))) : h("span", { class: "muted" }, "–")));
  });

  const exceptionForm = h("form", { class: "inline", onsubmit: async (event) => {
    event.preventDefault();
    const data = fields(event.target);
    const available = data.mode === "extra";
    const payload = {
      day: data.day, available, note: data.note || null,
      start_time: data.start_time || null, end_time: data.end_time || null,
    };
    if (await attempt(() => api("/api/availability/exceptions", { json: payload }), "Opgeslagen")) route();
  } },
    h("label", {}, "Datum", h("input", { name: "day", type: "date", required: true })),
    h("label", {}, "Wat", h("select", { name: "mode" }, h("option", { value: "off" }, "niet beschikbaar"), h("option", { value: "extra" }, "extra blok"))),
    h("label", {}, "Van (leeg = hele dag)", h("input", { name: "start_time", type: "time" })),
    h("label", {}, "Tot", h("input", { name: "end_time", type: "time" })),
    h("label", {}, "Notitie", h("input", { name: "note", placeholder: "bv. lange duurloop" })),
    h("button", { class: "primary" }, "Toevoegen"),
  );

  const today = new Date().toISOString().slice(0, 10);
  const upcoming = exceptions.filter((e) => e.day >= today).map((e) => h("tr", {},
    h("td", { class: "num" }, e.day),
    h("td", {}, e.available ? h("span", { class: "badge ok" }, "extra") : h("span", { class: "badge bad" }, "vrij")),
    h("td", { class: "num" }, e.start_time ? `${e.start_time}–${e.end_time}` : "hele dag"),
    h("td", { class: "muted" }, e.note || ""),
    h("td", { class: "right" }, h("button", { class: "link danger", onclick: async () => { if (await attempt(() => api(`/api/availability/exceptions/${e.id}`, { method: "DELETE" }))) route(); } }, "verwijderen")),
  ));

  return [
    h("h1", {}, "Beschikbaarheid"),
    card(`Weekpatroon · ${duration(weekly)} per week`,
      h("div", { class: "table-wrap" }, h("table", {}, h("tbody", {}, ...week))),
      h("h3", {}, "Blok toevoegen"), slotForm),
    card("Uitzonderingen",
      h("p", { class: "muted small" }, "Een dag of uur waarop je niet kunt, of een extra blok. Na een wijziging: herplan op de pagina Plan."),
      upcoming.length ? h("div", { class: "table-wrap" }, h("table", {}, h("tbody", {}, ...upcoming))) : null,
      exceptionForm),
  ];
}
