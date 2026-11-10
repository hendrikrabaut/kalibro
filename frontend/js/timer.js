import { api } from "./api.js";
import { attempt, h } from "./dom.js";
import { clock, duration, margin } from "./format.js";

export const getTimer = () => api("/api/timer");

export const startTask = (taskId) => attempt(() => api(`/api/tasks/${taskId}/start`, { method: "POST" }));
export const stopTimer = () => attempt(() => api("/api/timer/stop", { method: "POST" }));
export const completeTask = (taskId) =>
  attempt(() => api(`/api/tasks/${taskId}/complete`, { method: "POST" }), "Afgerond, goed bezig");

// A ticking card for the running session. Returns the node and a stop function for its interval.
export function timerCard(state, onChange) {
  if (!state.running) {
    return { node: h("section", { class: "timer" }, h("div", { class: "muted" }, "Geen timer actief"), h("div", { class: "elapsed" }, "00:00")), stop() {} };
  }
  const { task } = state;
  const startedAt = Date.now() - state.elapsed_s * 1000;
  const loggedBefore = task.logged_s - state.elapsed_s;
  const elapsed = h("div", { class: "elapsed" });
  const bar = h("span");
  const total = h("div", { class: "muted small" });

  function tick() {
    const running = (Date.now() - startedAt) / 1000;
    elapsed.textContent = clock(running);
    const spent = loggedBefore + running;
    if (task.estimate_s) {
      const share = spent / task.estimate_s;
      bar.style.width = `${Math.min(100, share * 100)}%`;
      bar.classList.toggle("over", share > 1);
      total.textContent = `${duration(spent)} van ${duration(task.estimate_s)} (marge ${margin(task)})`;
    } else {
      total.textContent = `${duration(spent)} gelogd`;
    }
  }
  tick();
  const interval = setInterval(tick, 1000);

  const node = h("section", { class: "timer" },
    h("div", { class: "muted" }, "Bezig met"),
    h("h2", {}, task.title),
    elapsed,
    h("div", { class: "progress" }, bar),
    total,
    h("div", { class: "row actions" },
      h("button", { onclick: async () => { await stopTimer(); onChange(); } }, "Pauze"),
      h("button", { class: "primary", onclick: async () => { await completeTask(task.id); onChange(); } }, "Afgerond"),
    ),
  );
  return { node, stop: () => clearInterval(interval) };
}
