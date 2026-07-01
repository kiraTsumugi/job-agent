export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";

export type StreamEvent = {
  event: string;
  data: unknown;
};

export type JDResponse = {
  id: string;
  title: string;
  company: string;
  raw_text: string;
};

export type UploadResponse = {
  token: string;
  filename: string;
  parsed_text: string;
};

export type ConversationSummary = {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
};

export type ConversationMessage = {
  role?: string;
  content?: string;
  [key: string]: unknown;
};

export type ConversationResponse = {
  id: string;
  title: string;
  messages: ConversationMessage[];
  created_at: string;
  updated_at: string;
};

export async function uploadResume(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE_URL}/api/upload`, {
    method: "POST",
    body: form
  });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}

export async function createJd(body: {
  title: string;
  company: string;
  raw_text: string;
}): Promise<JDResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jds`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}

export async function streamChat(
  body: {
    message: string;
    conversation_id?: string;
    resume_token?: string;
    jd_id?: string;
  },
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal
  });
  if (!response.ok || !response.body) {
    throw new Error(await readError(response));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop() || "";
    for (const part of parts) {
      const parsed = parseSse(part);
      if (parsed) onEvent(parsed);
    }
  }

  const tail = parseSse(buffer);
  if (tail) onEvent(tail);
}

function parseSse(chunk: string): StreamEvent | null {
  if (!chunk.trim()) return null;
  let event = "message";
  const dataLines: string[] = [];
  for (const line of chunk.split(/\r?\n/)) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (dataLines.length === 0) return null;
  const raw = dataLines.join("\n");
  try {
    return { event, data: JSON.parse(raw) };
  } catch {
    return { event, data: raw };
  }
}

async function readError(response: Response): Promise<string> {
  try {
    const data = await response.json();
    return data.detail || data.error || response.statusText;
  } catch {
    return response.statusText;
  }
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const response = await fetch(`${API_BASE_URL}/api/conversations`);
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}

export async function getConversation(id: string): Promise<ConversationResponse> {
  const response = await fetch(`${API_BASE_URL}/api/conversations/${encodeURIComponent(id)}`);
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}
