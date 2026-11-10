const TYPE_LABELS = {
  reading: "lezen", slides: "slides", exercises: "oefeningen", lab: "labo", review: "herhalen", other: "overig",
};
const UNIT_LABELS = { page: "p.", slide: "slides", exercise: "vragen", item: "×" };
const STATUS_LABELS = { open: "open", in_progress: "bezig", done: "af" };

export const typeLabel = (type) => TYPE_LABELS[type] || type;
export const unitLabel = (unit) => UNIT_LABELS[unit] || unit;
export const statusLabel = (status) => STATUS_LABELS[status] || status;
export const TASK_TYPES = Object.keys(TYPE_LABELS);

export function duration(seconds) {
  if (seconds === null || seconds === undefined) return "–";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} u ${String(rest).padStart(2, "0")}` : `${hours} u`;
}

// Margins are rounded more coarsely: "2–4 u" reads better than "1 u 42–4 u 11".
export function roughHours(seconds) {
  const hours = seconds / 3600;
  if (hours < 1) return `${Math.max(5, Math.round(seconds / 300) * 5)} min`;
  return `${hours < 10 ? Math.round(hours * 2) / 2 : Math.round(hours)} u`.replace(".", ",");
}

export function margin(task) {
  if (task.estimate_low_s === null) return "";
  return `${roughHours(task.estimate_low_s)} – ${roughHours(task.estimate_high_s)}`;
}

export function clock(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const hh = Math.floor(s / 3600);
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return hh ? `${hh}:${mm}:${ss}` : `${mm}:${ss}`;
}

const dayFormat = new Intl.DateTimeFormat("nl-BE", { weekday: "long", day: "numeric", month: "long" });
const shortFormat = new Intl.DateTimeFormat("nl-BE", { weekday: "short", day: "numeric", month: "short" });
const timeFormat = new Intl.DateTimeFormat("nl-BE", { hour: "2-digit", minute: "2-digit" });

export const day = (iso) => dayFormat.format(new Date(iso));
export const shortDay = (iso) => shortFormat.format(new Date(iso));
export const time = (iso) => timeFormat.format(new Date(iso));
export const dateTime = (iso) => `${shortDay(iso)} ${time(iso)}`;

export function localDateKey(iso) {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// <input type="datetime-local"> wants local time without an offset.
export function toLocalInput(iso) {
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export const fromLocalInput = (value) => new Date(value).toISOString();

export const WEEKDAYS = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"];

export const STATUS_TEXT = {
  ok: "haalbaar",
  tight: "krap: lukt alleen als het meevalt",
  infeasible: "niet haalbaar",
};
