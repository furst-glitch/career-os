import { createClient } from "@/lib/supabase";

// Normaliser: fjern eventuel /api/v1 suffix, tilføj altid /api/v1
// Håndterer både NEXT_PUBLIC_API_URL=http://localhost:8000
// og NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
const _base = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/api\/v1\/?$/, "");
const API_URL = `${_base}/api/v1`;

async function getAuthHeader(): Promise<Record<string, string>> {
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function extractError(res: Response, path: string): Promise<never> {
  const text = await res.text().catch(() => "");
  let detail = text;
  try {
    const json = JSON.parse(text);
    detail = json.detail ?? json.message ?? text;
  } catch {
    // use raw text
  }
  throw new Error(detail || `HTTP ${res.status} ${path}`);
}

export async function apiGet<T>(path: string): Promise<T> {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_URL}${path}`, { headers });
  if (!res.ok) return extractError(res, path);
  return res.json();
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) return extractError(res, path);
  return res.json();
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_URL}${path}`, {
    method: "PUT",
    headers: { ...headers, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) return extractError(res, path);
  return res.json();
}

export async function apiDelete(path: string): Promise<void> {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_URL}${path}`, { method: "DELETE", headers });
  if (!res.ok) return extractError(res, path);
}

const EXT_MIME: Record<string, string> = {
  pdf: "application/pdf",
  doc: "application/msword",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  txt: "text/plain",
};

export async function apiUpload<T>(path: string, file: File): Promise<T> {
  const headers = await getAuthHeader();
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  const mime = file.type || EXT_MIME[ext] || "application/octet-stream";
  const fileWithType = mime !== file.type ? new File([file], file.name, { type: mime }) : file;
  const form = new FormData();
  form.append("file", fileWithType);
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers, // Don't set Content-Type — browser adds boundary automatically
    body: form,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text || `API ${path}: ${res.status}`);
  }
  return res.json();
}

export type UploadProgressEvent = {
  step: string;
  pct: number;
  message: string;
};

/** Upload file and receive SSE progress events. Returns the final result from the "done" event. */
export async function apiUploadStream<T>(
  path: string,
  file: File,
  onProgress: (evt: UploadProgressEvent) => void,
): Promise<T> {
  const headers = await getAuthHeader();
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  const mime = file.type || EXT_MIME[ext] || "application/octet-stream";
  const fileWithType = mime !== file.type ? new File([file], file.name, { type: mime }) : file;
  const form = new FormData();
  form.append("file", fileWithType);

  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers,
    body: form,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text || `API ${path}: ${res.status}`);
  }
  if (!res.body) throw new Error("Ingen svar fra serveren");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const event of events) {
      const line = event.trim();
      // SSE keep-alive comments (": ping") — skip
      if (line.startsWith(":")) continue;
      if (!line.startsWith("data: ")) continue;
      const raw = line.slice(6);
      let payload: Record<string, unknown>;
      try {
        payload = JSON.parse(raw);
      } catch {
        continue;
      }
      if (payload.type === "progress") {
        onProgress({
          step: payload.step as string,
          pct: payload.pct as number,
          message: payload.message as string,
        });
      } else if (payload.type === "done") {
        return payload.data as T;
      } else if (payload.type === "error") {
        throw new Error((payload.message as string) || "Upload mislykkedes");
      }
    }
  }
  throw new Error("Ingen resultat modtaget fra serveren");
}

export type GenerateProgressEvent = {
  step: string;
  pct: number;
  msg: string;
};

export async function apiStream(
  path: string,
  body: unknown,
  onChunk: (content: string) => void,
  onDone?: (payload?: Record<string, unknown>) => void,
  onError?: (error: string) => void,
  onProgress?: (evt: GenerateProgressEvent) => void,
): Promise<void> {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    // Read error body so callers get a useful message instead of just "HTTP 422"
    const text = await res.text().catch(() => "");
    let detail = text;
    try { detail = (JSON.parse(text) as { detail?: string; message?: string }).detail ?? (JSON.parse(text) as { message?: string }).message ?? text; } catch { /* use raw text */ }
    throw new Error(detail || `HTTP ${res.status}`);
  }
  if (!res.body) return;

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let doneCalled = false;

  function dispatchEvent(event: string): void {
    // Skip SSE comment lines (": ping" keep-alive)
    if (event.trimStart().startsWith(":")) return;
    const dataLine = event.split("\n").find((l) => l.startsWith("data: "));
    if (!dataLine) return;
    try {
      const payload = JSON.parse(dataLine.slice(6)) as Record<string, unknown>;
      if (payload.type === "chunk" && payload.content) {
        onChunk(payload.content as string);
      } else if (payload.type === "progress") {
        onProgress?.({ step: payload.step as string, pct: payload.pct as number, msg: payload.msg as string });
      } else if (payload.type === "done") {
        doneCalled = true;
        onDone?.(payload);
      } else if (payload.type === "error") {
        onError?.(((payload.content ?? payload.message) as string | undefined) ?? "Ukendt fejl");
      }
    } catch {
      // Skip malformed SSE events
    }
  }

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      // Flush any bytes the TextDecoder was holding in streaming mode
      buffer += decoder.decode();
      break;
    }
    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by double newline
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    events.forEach(dispatchEvent);
  }

  // Process events that arrived in the same TCP frame as the stream-close signal.
  // This is the common case for the final "done" event — the server sends it and
  // immediately closes the connection, so it arrives with done=true from the reader.
  if (buffer.trim()) {
    buffer.split("\n\n").filter(Boolean).forEach(dispatchEvent);
  }

  // Fallback: backend closed the stream without sending a {"type":"done"} event.
  // Notify the caller so it can reset loading state and avoid a permanent spinner.
  if (!doneCalled) onDone?.();
}
