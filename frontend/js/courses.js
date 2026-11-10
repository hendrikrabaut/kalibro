import { api } from "./api.js";
import { attempt, card, fields, h, toast } from "./dom.js";
import { TASK_TYPES, dateTime, duration, fromLocalInput, margin, statusLabel, typeLabel, unitLabel } from "./format.js";
import { route } from "./main.js";
import { startTask } from "./timer.js";

export async function renderCourses() {
  const courses = await api("/api/courses");

  const form = h("form", { class: "inline", onsubmit: async (event) => {
    event.preventDefault();
    const data = fields(event.target);
    const course = await attempt(() => api("/api/courses", { json: { name: data.name, ical_url: data.ical_url || null } }), "Vak toegevoegd");
    if (course) location.hash = `vak/${course.id}`;
  } },
    h("label", {}, "Naam", h("input", { name: "name", required: true, placeholder: "Databanken" })),
    h("label", {}, "iCal-feed (optioneel)", h("input", { name: "ical_url", type: "url", placeholder: "https://…" })),
    h("button", { class: "primary" }, "Toevoegen"),
  );

  return [
    h("h1", {}, "Vakken"),
    card(null, courses.length
      ? h("div", { class: "table-wrap" }, h("table", {}, h("tbody", {}, ...courses.map((course) =>
          h("tr", {}, h("td", {}, h("a", { href: `#vak/${course.id}` }, course.name)), h("td", { class: "muted small" }, course.ical_url ? "feed gekoppeld" : ""))))))
      : h("p", { class: "muted" }, "Nog geen vakken. Voeg er een toe en upload een PDF.")),
    card("Nieuw vak", form),
  ];
}

export async function renderCourse(id) {
  const [course, sources, tasks, deadlines] = await Promise.all([
    api(`/api/courses/${id}`),
    api(`/api/courses/${id}/sources`),
    api(`/api/courses/${id}/tasks`),
    api(`/api/courses/${id}/deadlines`),
  ]);

  return [
    h("div", { class: "row spread" }, h("h1", {}, course.name), h("a", { href: "#vakken" }, "← alle vakken")),
    h("div", { class: "grid-2" }, uploadCard(course, sources), deadlineCard(course, deadlines)),
    taskCard(course, tasks, deadlines),
    settingsCard(course),
  ];
}

function uploadCard(course, sources) {
  const status = h("p", { class: "muted small" });
  const input = h("input", { type: "file", accept: "application/pdf,.pdf", required: true });
  const button = h("button", { class: "primary" }, "Uploaden");
  const form = h("form", { class: "inline", onsubmit: async (event) => {
    event.preventDefault();
    const file = input.files[0];
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    button.disabled = true;
    status.textContent = `Bezig met ${file.name}: structuur zoeken… (een groot boek kan op de Pi even duren)`;
    const result = await attempt(() => api(`/api/courses/${course.id}/sources`, { form: body }));
    button.disabled = false;
    status.textContent = "";
    if (result) {
      toast(`${result.page_count} pagina's, ${result.tasks.length} taken`, "ok");
      route();
    }
  } }, input, button);

  const methodText = { toc: "bladwijzers", fonts: "lettergrootte", none: "geen structuur gevonden" };
  const rows = sources.map((source) => h("tr", {},
    h("td", {}, source.filename),
    h("td", { class: "num" }, `${source.page_count} p.`),
    h("td", {}, source.scanned ? h("span", { class: "badge tight" }, "gescand") : h("span", { class: "muted small" }, methodText[source.structure_method])),
    h("td", { class: "right" },
      h("button", { class: "link", title: "Opnieuw verwerken met de huidige herkenning", onclick: async () => {
        if (await attempt(() => api(`/api/sources/${source.id}/reprocess`, { method: "POST" }), "Opnieuw verwerkt")) route();
      } }, "opnieuw"), " · ",
      h("button", { class: "link danger", onclick: async () => {
        if (!confirm(`${source.filename} en de taken eruit verwijderen?`)) return;
        if (await attempt(() => api(`/api/sources/${source.id}`, { method: "DELETE" }), "Verwijderd")) route();
      } }, "verwijderen")),
  ));

  return card("Cursusmateriaal",
    form, status,
    rows.length ? h("div", { class: "table-wrap" }, h("table", {}, h("tbody", {}, ...rows))) : h("p", { class: "muted small" }, "PDF met tekstlaag; gescande bestanden worden gemarkeerd om zelf te schatten."),
  );
}

function deadlineCard(course, deadlines) {
  const form = h("form", { class: "inline", onsubmit: async (event) => {
    event.preventDefault();
    const data = fields(event.target);
    const payload = { title: data.title, due_at: fromLocalInput(data.due_at), kind: data.kind };
    if (await attempt(() => api(`/api/courses/${course.id}/deadlines`, { json: payload }), "Deadline toegevoegd")) route();
  } },
    h("label", {}, "Titel", h("input", { name: "title", required: true })),
    h("label", {}, "Wanneer", h("input", { name: "due_at", type: "datetime-local", required: true })),
    h("label", {}, "Soort", h("select", { name: "kind" }, h("option", { value: "assignment" }, "opdracht"), h("option", { value: "exam" }, "examen"))),
    h("button", { class: "primary" }, "Toevoegen"),
  );

  const sync = course.ical_url
    ? h("button", { onclick: async () => {
        const result = await attempt(() => api(`/api/courses/${course.id}/deadlines/sync`, { method: "POST" }));
        if (result) { toast(`${result.added} nieuw, ${result.updated} gewijzigd`, "ok"); route(); }
      } }, "Ophalen uit feed")
    : null;

  const rows = deadlines.map((d) => h("tr", {},
    h("td", {}, d.kind === "exam" ? h("b", {}, d.title) : d.title, d.origin === "ical" ? h("span", { class: "muted small" }, " · feed") : null),
    h("td", { class: "num" }, dateTime(d.due_at)),
    h("td", { class: "right" }, h("button", { class: "link danger", onclick: async () => {
      if (await attempt(() => api(`/api/deadlines/${d.id}`, { method: "DELETE" }))) route();
    } }, d.origin === "ical" ? "negeren" : "verwijderen")),
  ));

  return card("Deadlines",
    h("div", { class: "row spread" }, h("span", { class: "muted small" }, "Koppel taken aan een deadline in de tabel hieronder."), sync),
    rows.length ? h("div", { class: "table-wrap" }, h("table", {}, h("tbody", {}, ...rows))) : null,
    form,
  );
}

function taskCard(course, tasks, deadlines) {
  const deadlineSelect = (task) => h("select", { onchange: async (event) => {
    const value = event.target.value ? Number(event.target.value) : null;
    if (await attempt(() => api(`/api/tasks/${task.id}`, { method: "PATCH", json: { deadline_id: value } }))) route();
  } },
    h("option", { value: "" }, "–"),
    ...deadlines.map((d) => h("option", { value: d.id, selected: d.id === task.deadline_id }, d.title)),
  );

  const editEstimate = (task) => h("button", { class: "link small", title: "Eigen schatting (minuten); leeg = automatisch", onclick: async () => {
    const current = task.manual_estimate_s ? Math.round(task.manual_estimate_s / 60) : "";
    const answer = prompt("Eigen schatting in minuten (leeg = automatisch)", current);
    if (answer === null) return;
    const value = answer.trim() === "" ? null : Math.round(Number(answer) * 60);
    if (Number.isNaN(value)) return toast("Geef een getal in", "error");
    if (await attempt(() => api(`/api/tasks/${task.id}`, { method: "PATCH", json: { manual_estimate_s: value } }))) route();
  } }, "✎");

  const estimateCell = (task) => task.needs_manual_estimate
    ? h("td", { class: "right nowrap" }, h("span", { class: "badge tight" }, "zelf schatten"), " ", editEstimate(task))
    : h("td", { class: "right num nowrap", title: `basis ${duration(task.base_estimate_s)} × ${task.factor}` },
        duration(task.estimate_s), " ", editEstimate(task),
        h("div", { class: "muted small" }, margin(task)));

  const assignAll = deadlines.length
    ? h("form", { class: "inline", onsubmit: async (event) => {
        event.preventDefault();
        const deadlineId = Number(fields(event.target).deadline);
        const open = tasks.filter((t) => t.status !== "done" && !t.deadline_id);
        for (const task of open) await api(`/api/tasks/${task.id}`, { method: "PATCH", json: { deadline_id: deadlineId } });
        toast(`${open.length} taken gekoppeld`, "ok");
        route();
      } },
        h("label", {}, "Alle taken zonder deadline koppelen aan", h("select", { name: "deadline" }, ...deadlines.map((d) => h("option", { value: d.id }, d.title)))),
        h("button", {}, "Koppelen"))
    : null;

  const rows = tasks.map((task) => h("tr", { class: task.status === "done" ? "done" : "" },
    h("td", { class: "title" }, task.title),
    h("td", {}, typeLabel(task.task_type)),
    h("td", { class: "right num nowrap" }, `${task.amount} ${unitLabel(task.unit)}`),
    estimateCell(task),
    h("td", { class: "right num" }, task.logged_s ? duration(task.logged_s) : ""),
    h("td", {}, deadlineSelect(task)),
    h("td", {}, statusLabel(task.status)),
    h("td", { class: "right nowrap" },
      task.status === "done"
        ? h("button", { class: "link", onclick: async () => { if (await attempt(() => api(`/api/tasks/${task.id}`, { method: "PATCH", json: { status: "in_progress" } }))) route(); } }, "heropen")
        : h("button", { onclick: async () => { if (await startTask(task.id)) location.hash = "vandaag"; } }, "Start"),
      " ",
      h("button", { class: "link danger", title: "Taak verwijderen", onclick: async () => {
        if (!confirm(`"${task.title}" verwijderen?`)) return;
        if (await attempt(() => api(`/api/tasks/${task.id}`, { method: "DELETE" }))) route();
      } }, "×")),
  ));

  const total = tasks.filter((t) => t.status !== "done").reduce((sum, t) => sum + (t.remaining_s || 0), 0);

  const addForm = h("form", { class: "inline", onsubmit: async (event) => {
    event.preventDefault();
    const data = fields(event.target);
    const payload = {
      title: data.title, task_type: data.task_type, amount: Number(data.amount || 1),
      manual_estimate_s: data.minutes ? Math.round(Number(data.minutes) * 60) : null,
      deadline_id: data.deadline_id ? Number(data.deadline_id) : null,
    };
    if (await attempt(() => api(`/api/courses/${course.id}/tasks`, { json: payload }), "Taak toegevoegd")) route();
  } },
    h("label", {}, "Taak", h("input", { name: "title", required: true, placeholder: "Labo 3" })),
    h("label", {}, "Type", h("select", { name: "task_type" }, ...TASK_TYPES.map((t) => h("option", { value: t, selected: t === "lab" }, typeLabel(t))))),
    h("label", {}, "Omvang", h("input", { name: "amount", type: "number", min: "0", step: "any", value: "1", style: "width:6em" })),
    h("label", {}, "Of eigen schatting (min)", h("input", { name: "minutes", type: "number", min: "0", style: "width:8em" })),
    h("label", {}, "Deadline", h("select", { name: "deadline_id" }, h("option", { value: "" }, "–"), ...deadlines.map((d) => h("option", { value: d.id }, d.title)))),
    h("button", { class: "primary" }, "Toevoegen"),
  );

  return card(`Taken · nog ${duration(total)}`,
    assignAll,
    rows.length
      ? h("div", { class: "table-wrap" }, h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Taak"), h("th", {}, "Type"), h("th", { class: "right" }, "Omvang"), h("th", { class: "right" }, "Schatting"), h("th", { class: "right" }, "Gelogd"), h("th", {}, "Deadline"), h("th", {}, "Status"), h("th", {}))),
          h("tbody", {}, ...rows)))
      : h("p", { class: "muted" }, "Nog geen taken. Upload een PDF of voeg er zelf een toe."),
    h("h3", {}, "Taak toevoegen"),
    addForm,
  );
}

function settingsCard(course) {
  const form = h("form", { class: "inline", onsubmit: async (event) => {
    event.preventDefault();
    const data = fields(event.target);
    const payload = { name: data.name, ical_url: data.ical_url || null, color: course.color, credits: data.credits ? Number(data.credits) : null };
    if (await attempt(() => api(`/api/courses/${course.id}`, { method: "PUT", json: payload }), "Opgeslagen")) route();
  } },
    h("label", {}, "Naam", h("input", { name: "name", value: course.name, required: true })),
    h("label", {}, "Studiepunten", h("input", { name: "credits", type: "number", min: "0", step: "any", value: course.credits ?? "", style: "width:6em" })),
    h("label", {}, "iCal-feed van het leerplatform", h("input", { name: "ical_url", type: "url", value: course.ical_url ?? "", style: "min-width:22em" })),
    h("button", {}, "Opslaan"),
  );
  const remove = h("button", { class: "danger", onclick: async () => {
    if (!confirm(`${course.name} met alle bestanden, taken en gelogde tijd verwijderen?`)) return;
    if (await attempt(() => api(`/api/courses/${course.id}`, { method: "DELETE" }), "Vak verwijderd")) location.hash = "vakken";
  } }, "Vak verwijderen");
  return card("Instellingen", form, h("p", {}), remove);
}
