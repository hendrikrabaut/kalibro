function errorText(detail) {
  if (Array.isArray(detail)) return detail.map((item) => `${item.loc.at(-1)}: ${item.msg}`).join("; ");
  return detail || "Er ging iets mis";
}

// json: sent as JSON (POST unless method says otherwise). form: sent as multipart.
export async function api(path, options = {}) {
  const init = { method: options.method || "GET" };
  if (options.json !== undefined) {
    init.method = options.method || "POST";
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(options.json);
  } else if (options.form !== undefined) {
    init.method = "POST";
    init.body = options.form;
  }

  let response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new Error("De server is niet bereikbaar");
  }
  if (response.status === 204) return true; // truthy, so callers can tell success from failure
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(errorText(body?.detail));
  return body;
}
