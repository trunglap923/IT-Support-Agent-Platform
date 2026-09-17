import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  createConversation,
  listConversations,
  listMessages,
  submitMessage,
  submitMessageFeedback,
  type ChatMessage,
  type Conversation,
} from "../../api/chat";
import {
  decideApproval,
  listPendingApprovals,
  type Approval,
} from "../../api/tickets";
import { useAuth } from "../auth/useAuth";
import { ApprovalCard } from "../tickets/ApprovalCard";
import { recoverActiveRun } from "./chatRecovery";
import { RunStatusPanel } from "./RunStatusPanel";

export function ChatPage() {
  const { csrfToken } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [active, setActive] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [draft, setDraft] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [feedbackPending, setFeedbackPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshConversation = useCallback(async (conversationId: string) => {
    const [messageItems, approvalItems] = await Promise.all([
      listMessages(conversationId),
      listPendingApprovals(),
    ]);
    setMessages(messageItems);
    setApprovals(approvalItems);
    setRunId(recoverActiveRun(messageItems, approvalItems));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void listConversations(controller.signal)
      .then(async (items) => {
        setConversations(items);
        if (items[0]) {
          setActive(items[0]);
          const [messageItems, approvalItems] = await Promise.all([
            listMessages(items[0].id, controller.signal),
            listPendingApprovals(controller.signal),
          ]);
          setMessages(messageItems);
          setApprovals(approvalItems);
          setRunId(recoverActiveRun(messageItems, approvalItems));
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
      setApprovals([]);
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
      await refreshConversation(conversation.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể gửi tin nhắn.");
    } finally {
      setSending(false);
    }
  }

  async function handleApprovalDecision(
    approval: Approval,
    decision: "approve" | "reject",
  ) {
    if (!csrfToken) return;
    setError(null);
    try {
      await decideApproval(approval, decision, csrfToken);
      setApprovals((current) => current.filter((item) => item.id !== approval.id));
      if (active) await refreshConversation(active.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể xử lý phê duyệt.");
    }
  }

  const handleRunStatus = useCallback(
    (status: string) => {
      if (status === "waiting_approval" && active) {
        void refreshConversation(active.id);
      }
    },
    [active, refreshConversation],
  );

  async function handleFeedback(
    messageId: string,
    rating: "helpful" | "unhelpful",
  ) {
    if (!active || !csrfToken || feedbackPending) return;
    setFeedbackPending(messageId);
    setError(null);
    try {
      const feedback = await submitMessageFeedback(active.id, messageId, rating, csrfToken);
      setMessages((current) =>
        current.map((message) =>
          message.id === messageId ? { ...message, feedback } : message,
        ),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể lưu phản hồi.");
    } finally {
      setFeedbackPending(null);
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
              void refreshConversation(conversation.id);
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
                      {source.source_url ? (
                        <a href={source.source_url} rel="noopener" target="_blank">
                          <strong>{source.title}</strong>
                        </a>
                      ) : (
                        <strong>{source.title}</strong>
                      )}
                      {source.page_number ? ` · Trang ${source.page_number}` : ""}
                      <small>{source.excerpt}</small>
                    </li>
                  ))}
                </ul>
              ) : null}
              {message.role === "assistant" ? (
                <div className="message-feedback" aria-label="Đánh giá câu trả lời">
                  <span>Câu trả lời này có hữu ích không?</span>
                  <button
                    aria-pressed={message.feedback?.rating === "helpful"}
                    disabled={feedbackPending === message.id}
                    onClick={() => void handleFeedback(message.id, "helpful")}
                    type="button"
                  >
                    Hữu ích
                  </button>
                  <button
                    aria-pressed={message.feedback?.rating === "unhelpful"}
                    disabled={feedbackPending === message.id}
                    onClick={() => void handleFeedback(message.id, "unhelpful")}
                    type="button"
                  >
                    Chưa tốt
                  </button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
        {runId ? (
          <RunStatusPanel
            runId={runId}
            onStatus={handleRunStatus}
            onTerminal={() => {
              if (active) void refreshConversation(active.id);
              setRunId(null);
            }}
          />
        ) : null}
        {approvals
          .filter((approval) => approval.run_id === runId)
          .map((approval) => (
            <ApprovalCard
              approval={approval}
              key={approval.id}
              onDecision={(decision) => handleApprovalDecision(approval, decision)}
            />
          ))}
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
