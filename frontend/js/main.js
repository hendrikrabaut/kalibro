import { h } from "./dom.js";
import { renderToday } from "./today.js";
import { renderCourses, renderCourse } from "./courses.js";
import { renderPlan } from "./plan.js";
import { renderAvailability } from "./availability.js";
import { renderCalibration } from "./calibration.js";

const VIEWS = {
  vandaag: renderToday,
  vakken: renderCourses,
  vak: renderCourse,
  plan: renderPlan,
  beschikbaarheid: renderAvailability,
  kalibratie: renderCalibration,
};

let cleanup = null;

export async function route() {
  const [name, param] = (location.hash.slice(1) || "vandaag").split("/");
  const view = VIEWS[name] || renderToday;
  document.querySelectorAll(".site-header nav a").forEach((link) => {
    const active = link.dataset.view === name || (name === "vak" && link.dataset.view === "vakken");
    link.classList.toggle("active", active);
  });

  if (cleanup) cleanup();
  cleanup = null;
  const app = document.getElementById("app");
  try {
    const result = await view(param);
    app.replaceChildren(...(result.nodes || result));
    cleanup = result.cleanup || null;
  } catch (error) {
    app.replaceChildren(h("section", { class: "card" }, h("h2", {}, "Kon dit niet laden"), h("p", {}, error.message)));
  }
}

addEventListener("hashchange", route);
route();
