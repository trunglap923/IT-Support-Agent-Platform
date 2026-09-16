import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  createConversation,
  listConversations,
  listMessages,
  submitMessage,
  type ChatMessage,
  type Conversation,
} from "../../api/chat";
import { useAuth } from "../auth/useAuth";
import { RunStatusPanel } from "./RunStatusPanel";

export function ChatPage() {
  const { csrfToken } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [active, setActive] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshMessages = useCallback(async (conversationId: string) => {
    setMessages(await listMessages(conversationId));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void listConversations(controller.signal)
      .then(async (items) => {
        setConversations(items);
        if (items[0]) {
          setActive(items[0]);
          setMessages(await listMessages(items[0].id, controller.signal));
        }
      })
      .catch((caught: unknown) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setError(caught instanceof Error ? caught.message : "Không thể tải hội thoại.");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  async function startConversation() {
    if (!csrfToken) return;
    setError(null);
    try {
      const created = await createConversation(csrfToken);
      setConversations((current) => [created, ...current]);
      setActive(created);
      setMessages([]);
      setRunId(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể tạo hội thoại.");
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || !csrfToken || sending) return;
    setSending(true);
    setError(null);
    try {
      let conversation = active;
      if (!conversation) {
        conversation = await createConversation(csrfToken);
        setConversations((current) => [conversation!, ...current]);
        setActive(conversation);
      }
      const submitted = await submitMessage(conversation.id, content, csrfToken);
      setDraft("");
      setRunId(submitted.run_id);
      await refreshMessages(conversation.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể gửi tin nhắn.");
    } finally {
      setSending(false);
    }
  }

  if (loading) return <p className="chat-loading">Đang tải cuộc trò chuyện…</p>;

  return (
    <div className="chat-layout">
      <aside className="conversation-list">
        <button className="new-chat-button" onClick={startConversation} type="button">
          + Cuộc trò chuyện mới
        </button>
        {conversations.map((conversation) => (
          <button
            className={conversation.id === active?.id ? "active" : ""}
            key={conversation.id}
            onClick={() => {
              setActive(conversation);
              setRunId(null);
              void refreshMessages(conversation.id);
            }}
            type="button"
          >
            {conversation.title}
          </button>
        ))}
      </aside>
      <section className="chat-panel">
        <header>
          <p className="eyebrow">AI SUPPORT · EVIDENCE FIRST</p>
          <h1>{active?.title ?? "Hỏi trợ lý IT"}</h1>
        </header>
        <div className="message-list" aria-live="polite">
          {messages.length === 0 ? (
            <div className="chat-empty">
              <strong>Bạn đang gặp vấn đề gì?</strong>
              <p>Hãy mô tả lỗi, thiết bị và thao tác bạn đã thử.</p>
            </div>
          ) : null}
          {messages.map((message) => (
            <article className={`chat-message ${message.role}`} key={message.id}>
              <span>{message.role === "user" ? "Bạn" : "IT Assistant"}</span>
              <p>{message.content}</p>
              {message.citations?.length ? (
                <ul className="citation-list">
                  {message.citations.map((source) => (
                    <li key={source.source_id}>
                      <strong>{source.title}</strong>
                      {source.page_number ? ` · Trang ${source.page_number}` : ""}
                      <small>{source.excerpt}</small>
                    </li>
                  ))}
                </ul>
              ) : null}
            </article>
          ))}
        </div>
        {runId ? (
          <RunStatusPanel
            runId={runId}
            onTerminal={() => {
              if (active) void refreshMessages(active.id);
              setRunId(null);
            }}
          />
        ) : null}
        {error ? (
          <p className="chat-error" role="alert">{error}</p>
        ) : null}
        <form className="chat-composer" onSubmit={handleSubmit}>
          <label className="sr-only" htmlFor="chat-input">Tin nhắn</label>
          <textarea
            disabled={sending || Boolean(runId)}
            id="chat-input"
            maxLength={4000}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Ví dụ: Tôi không kết nối được VPN trên Ubuntu…"
            rows={3}
            value={draft}
          />
          <button disabled={!draft.trim() || sending || Boolean(runId)} type="submit">
            {sending ? "Đang gửi…" : "Gửi"}
          </button>
        </form>
      </section>
    </div>
  );
}
