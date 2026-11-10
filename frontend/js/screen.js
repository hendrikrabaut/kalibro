import { api } from "./api.js";
import { h } from "./dom.js";
import { day, duration, localDateKey, time } from "./format.js";
import { getTimer, startTask, timerCard } from "./timer.js";

const REFRESH_MS = 30_000;
const MAX_CHOICES = 4;
let stopTicking = () => {};

function updateClock() {
  const now = new Date();
  document.getElementById("screen-clock").textContent = now.toLocaleTimeString("nl-BE", { hour: "2-digit", minute: "2-digit" });
  document.getElementById("screen-date").textContent = day(now.toISOString());
}

// Today's planned tasks first, then the next ones in the plan, without duplicates.
function choices(plan) {
  const today = localDateKey(new Date().toISOString());
  const now = Date.now();
  const seen = new Set();
  const picked = [];
  const upcoming = plan.blocks.filter((b) => !b.done && new Date(b.end_at) > now);
  const ordered = [...upcoming.filter((b) => localDateKey(b.start_at) === today), ...upcoming];
  for (const block of ordered) {
    if (seen.has(block.task_id)) continue;
    seen.add(block.task_id);
    picked.push(block);
    if (picked.length === MAX_CHOICES) break;
  }
  return { picked, today };
}

async function render() {
  const status = document.getElementById("screen-status");
  try {
    const [timer, plan] = await Promise.all([getTimer(), api("/api/plan")]);
    stopTicking();
    const view = timerCard(timer, render);
    stopTicking = view.stop;

    const nodes = [view.node];
    if (!timer.running) {
      const { picked, today } = choices(plan);
      nodes.push(picked.length
        ? h("div", { class: "pick" }, ...picked.map((block) => h("button", { onclick: async () => { await startTask(block.task_id); render(); } },
            block.title,
            h("small", {}, localDateKey(block.start_at) === today ? `vandaag ${time(block.start_at)}–${time(block.end_at)}` : `gepland ${day(block.start_at)}`))))
        : h("p", { class: "muted" }, "Niets gepland. Maak een plan op de laptop."));
    }
    const late = plan.late_tasks.length ? ` · ${plan.late_tasks.length} taken te laat` : "";
    status.textContent = `Nog ${duration(plan.work_s)} te doen${late} · bijgewerkt ${time(new Date().toISOString())}`;
    document.getElementById("screen").replaceChildren(...nodes);
  } catch (error) {
    status.textContent = `Geen verbinding: ${error.message}`;
  }
}

updateClock();
setInterval(updateClock, 10_000);
render();
setInterval(render, REFRESH_MS);
