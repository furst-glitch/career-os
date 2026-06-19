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

export async function apiStream(
  path: string,
  body: unknown,
  onChunk: (content: string) => void,
  onDone?: () => void,
  onError?: (error: string) => void
): Promise<void> {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) throw new Error(`API ${path}: ${res.status}`);
  if (!res.body) return;

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by double newline
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const event of events) {
      const dataLine = event.split("\n").find((l) => l.startsWith("data: "));
      if (!dataLine) continue;
      try {
        const payload = JSON.parse(dataLine.slice(6));
        if (payload.type === "chunk" && payload.content) {
          onChunk(payload.content);
        } else if (payload.type === "done") {
          onDone?.();
        } else if (payload.type === "error") {
          onError?.(payload.content);
        }
      } catch {
        // Skip malformed events
      }
    }
  }
}
