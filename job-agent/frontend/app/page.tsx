"use client";

import { FormEvent, useMemo, useRef, useState } from "react";
import { FileUp, Play, Save, Square, Wand2 } from "lucide-react";
import { createJd, streamChat, StreamEvent, uploadResume } from "../lib/api";

type Message = {
  role: "user" | "assistant";
  content: string;
};

const SAMPLE_JD = `岗位：AI Agent 实习生
要求：
- 熟悉 Python、FastAPI、PostgreSQL
- 有 RAG、向量检索、Qdrant 或 LangGraph 项目经验
- 能做 Prompt 版本管理、评测和 badcase 分析
- 有前端或部署经验加分`;

export default function HomePage() {
  const [resumeToken, setResumeToken] = useState("");
  const [resumeName, setResumeName] = useState("");
  const [jdId, setJdId] = useState("");
  const [jdTitle, setJdTitle] = useState("AI Agent 实习生");
  const [company, setCompany] = useState("Demo Company");
  const [jdText, setJdText] = useState(SAMPLE_JD);
  const [message, setMessage] = useState("请分析我的简历和目标 JD 的匹配度，并列出关键 gap。");
  const [conversationId, setConversationId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  const finalOutput = useMemo(() => {
    const complete = [...events].reverse().find((item) => item.event === "complete");
    return complete ? JSON.stringify(complete.data, null, 2) : "";
  }, [events]);

  async function onUpload(file?: File) {
    if (!file) return;
    setError("");
    setBusy(true);
    try {
      const result = await uploadResume(file);
      setResumeToken(result.token);
      setResumeName(result.filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  async function onSaveJd() {
    setError("");
    setBusy(true);
    try {
      const result = await createJd({
        title: jdTitle.trim() || "Untitled JD",
        company: company.trim() || "Unknown",
        raw_text: jdText
      });
      setJdId(result.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存 JD 失败");
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!message.trim()) return;
    const userMessage = message.trim();
    setError("");
    setBusy(true);
    setEvents([]);
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    abortRef.current = new AbortController();

    try {
      await streamChat(
        {
          message: userMessage,
          conversation_id: conversationId || undefined,
          resume_token: resumeToken || undefined,
          jd_id: jdId || undefined
        },
        (item) => {
          setEvents((prev) => [...prev, item]);
          if (item.event === "conversation" && isRecord(item.data)) {
            const id = item.data.conversation_id;
            if (typeof id === "string") setConversationId(id);
          }
          if (item.event === "complete") {
            setMessages((prev) => [
              ...prev,
              { role: "assistant", content: JSON.stringify(item.data, null, 2) }
            ]);
          }
          if (item.event === "error" && isRecord(item.data)) {
            setError(String(item.data.error || "Agent 调用失败"));
          }
        },
        abortRef.current.signal
      );
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        setError(err instanceof Error ? err.message : "请求失败");
      }
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  }

  function stopStream() {
    abortRef.current?.abort();
    setBusy(false);
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>AI 求职助手</h1>
          <p>Resume x JD Agent</p>
        </div>
        <div className="status">
          <span>{resumeToken ? "Resume linked" : "No resume"}</span>
          <span>{jdId ? "JD saved" : "JD draft"}</span>
        </div>
      </header>

      <section className="workspace">
        <aside className="panel setup-panel">
          <div className="section-head">
            <h2>Input</h2>
          </div>

          <label className="upload-box">
            <FileUp size={18} />
            <span>{resumeName || "PDF / DOCX"}</span>
            <input
              type="file"
              accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(event) => onUpload(event.target.files?.[0])}
            />
          </label>

          <div className="field-row">
            <label>
              <span>Title</span>
              <input value={jdTitle} onChange={(event) => setJdTitle(event.target.value)} />
            </label>
            <label>
              <span>Company</span>
              <input value={company} onChange={(event) => setCompany(event.target.value)} />
            </label>
          </div>

          <label className="field">
            <span>JD</span>
            <textarea value={jdText} onChange={(event) => setJdText(event.target.value)} />
          </label>

          <button className="button secondary" type="button" onClick={onSaveJd} disabled={busy}>
            <Save size={16} />
            <span>Save JD</span>
          </button>
        </aside>

        <section className="panel chat-panel">
          <div className="section-head">
            <h2>Agent</h2>
            <button className="icon-button" type="button" onClick={stopStream} disabled={!busy} title="Stop">
              <Square size={16} />
            </button>
          </div>

          <div className="messages">
            {messages.length === 0 ? (
              <div className="empty-state">Ready</div>
            ) : (
              messages.map((item, index) => (
                <article className={`message ${item.role}`} key={`${item.role}-${index}`}>
                  <strong>{item.role === "user" ? "You" : "Agent"}</strong>
                  <pre>{item.content}</pre>
                </article>
              ))
            )}
          </div>

          <form className="composer" onSubmit={onSubmit}>
            <textarea value={message} onChange={(event) => setMessage(event.target.value)} />
            <button className="button primary" type="submit" disabled={busy}>
              {busy ? <Wand2 size={16} /> : <Play size={16} />}
              <span>{busy ? "Running" : "Run"}</span>
            </button>
          </form>
        </section>

        <aside className="panel output-panel">
          <div className="section-head">
            <h2>Trace</h2>
          </div>
          <ol className="event-list">
            {events.map((item, index) => (
              <li key={`${item.event}-${index}`}>
                <span>{item.event}</span>
              </li>
            ))}
          </ol>
          <pre className="result">{finalOutput || error || "No output"}</pre>
        </aside>
      </section>
    </main>
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
