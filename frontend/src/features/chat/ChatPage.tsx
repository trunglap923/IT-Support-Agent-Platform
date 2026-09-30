import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import {
  createConversation,
  listConversationsPage,
  listMessagesPage,
  submitMessage,
  submitMessageFeedback,
  type ChatMessage,
  type Conversation,
} from "../../api/chat";
import {
  decideApproval,
  listPendingApprovalsPage,
  type Approval,
} from "../../api/tickets";
import { cancelRun, getRunSnapshot } from "../../api/run-events";
import { getOrCreateClientRequest, type ClientRequestIdentity } from "../../api/idempotency";
import { useAuth } from "../auth/useAuth";
import { LoadingState } from "../../components/ProductUI";
import { ApprovalCard } from "../tickets/ApprovalCard";
import { formatTicketDraftForChat } from "../tickets/approvalEdit";
import { CitationList } from "./CitationList";
import { recoverActiveRun } from "./chatRecovery";
import { RunStatusPanel } from "./RunStatusPanel";
import { SafeMarkdown } from "./SafeMarkdown";

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
  const [notice, setNotice] = useState<string | null>(null);
  const [conversationCursor, setConversationCursor] = useState<string | null>(null);
  const [messageCursor, setMessageCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState<"conversations" | "messages" | null>(null);
  const [conversationQuery, setConversationQuery] = useState("");
  const pendingMessageRequest = useRef<ClientRequestIdentity | null>(null);

  const visibleConversations = useMemo(() => conversations.filter((conversation) =>
    conversation.title.toLocaleLowerCase().includes(conversationQuery.trim().toLocaleLowerCase()),
  ), [conversationQuery, conversations]);
  const contextSources = useMemo(() => {
    const unique = new Map<string, NonNullable<ChatMessage["citations"]>[number]>();
    for (const message of [...messages].reverse()) {
      for (const citation of message.citations ?? []) {
        const key = citation.document_id ?? citation.source_id;
        if (!unique.has(key)) unique.set(key, citation);
      }
    }
    return [...unique.values()].slice(0, 4);
  }, [messages]);

  const refreshConversation = useCallback(async (conversationId: string) => {
    const [messagePage, approvalPage] = await Promise.all([
      listMessagesPage(conversationId),
      listPendingApprovalsPage(),
    ]);
    setMessages(messagePage.items);
    setMessageCursor(messagePage.next_cursor);
    setApprovals(approvalPage.items);
    setRunId(recoverActiveRun(messagePage.items, approvalPage.items));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void listConversationsPage(null, controller.signal)
      .then(async (page) => {
        setConversations(page.items);
        setConversationCursor(page.next_cursor);
        if (page.items[0]) {
          setActive(page.items[0]);
          const [messagePage, approvalPage] = await Promise.all([
            listMessagesPage(page.items[0].id, null, controller.signal),
            listPendingApprovalsPage(null, controller.signal),
          ]);
          setMessages(messagePage.items);
          setMessageCursor(messagePage.next_cursor);
          setApprovals(approvalPage.items);
          setRunId(recoverActiveRun(messagePage.items, approvalPage.items));
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
    setNotice(null);
    try {
      const created = await createConversation(csrfToken);
      setConversations((current) => [created, ...current]);
      setActive(created);
      setMessages([]);
      setMessageCursor(null);
      setApprovals([]);
      setRunId(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể tạo hội thoại.");
    }
  }

  async function loadMoreConversations() {
    if (!conversationCursor || loadingMore) return;
    setLoadingMore("conversations");
    setError(null);
    try {
      const page = await listConversationsPage(conversationCursor);
      setConversations((current) => [...current, ...page.items]);
      setConversationCursor(page.next_cursor);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể tải thêm hội thoại.");
    } finally {
      setLoadingMore(null);
    }
  }

  async function loadOlderMessages() {
    if (!active || !messageCursor || loadingMore) return;
    setLoadingMore("messages");
    setError(null);
    try {
      const page = await listMessagesPage(active.id, messageCursor);
      setMessages((current) => [...page.items, ...current]);
      setMessageCursor(page.next_cursor);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể tải tin nhắn cũ hơn.");
    } finally {
      setLoadingMore(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || !csrfToken || sending) return;
    setSending(true);
    setError(null);
    setNotice(null);
    try {
      let conversation = active;
      if (!conversation) {
        conversation = await createConversation(csrfToken);
        setConversations((current) => [conversation!, ...current]);
        setActive(conversation);
      }
      const request = getOrCreateClientRequest(
        pendingMessageRequest.current,
        JSON.stringify([conversation.id, content]),
      );
      pendingMessageRequest.current = request;
      const submitted = await submitMessage(conversation.id, content, csrfToken, request.id);
      pendingMessageRequest.current = null;
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
    setNotice(null);
    try {
      await decideApproval(approval, decision, csrfToken);
      setApprovals((current) => current.filter((item) => item.id !== approval.id));
      if (active) await refreshConversation(active.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể xử lý phê duyệt.");
    }
  }

  async function handleApprovalEdit(approval: Approval) {
    if (!csrfToken) return;
    setError(null);
    setNotice(null);
    try {
      const run = await getRunSnapshot(approval.run_id);
      await cancelRun(run.id, run.version, csrfToken, "draft_replaced");
      setApprovals((current) => current.filter((item) => item.id !== approval.id));
      setRunId(null);
      setDraft(formatTicketDraftForChat(approval.canonical_args));
      setNotice("Đã hủy bản nháp cũ. Hãy chỉnh sửa nội dung rồi gửi để tạo bản nháp mới.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể sửa bản nháp.");
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

  if (loading) return <LoadingState label="Đang tải cuộc trò chuyện…" />;

  return (
    <div className="chat-layout">
      <aside className="conversation-list">
        <button className="new-chat-button" onClick={startConversation} type="button">
          + Cuộc trò chuyện mới
        </button>
        <label className="conversation-search"><span aria-hidden="true">⌕</span><span className="sr-only">Tìm cuộc trò chuyện</span><input onChange={(event) => setConversationQuery(event.target.value)} placeholder="Tìm cuộc trò chuyện…" type="search" value={conversationQuery} /></label>
        <p className="conversation-period">Gần đây</p>
        {visibleConversations.map((conversation) => (
          <button
            className={conversation.id === active?.id ? "active" : ""}
            key={conversation.id}
            onClick={() => {
              setActive(conversation);
              void refreshConversation(conversation.id);
            }}
            type="button"
          >
            <span aria-hidden="true">○</span><strong>{conversation.title}</strong>
          </button>
        ))}
        {conversationCursor ? (
          <button
            className="load-more-button"
            disabled={Boolean(loadingMore)}
            onClick={() => void loadMoreConversations()}
            type="button"
          >
            {loadingMore === "conversations" ? "Đang tải…" : "Tải thêm hội thoại"}
          </button>
        ) : null}
      </aside>
      <section className="chat-panel">
        <header>
          <span className="assistant-mark" aria-hidden="true">✦</span>
          <div><h1>Trợ lý AI</h1><p>{active?.title ?? "Hỏi đáp hỗ trợ IT dựa trên tài liệu nội bộ"}</p></div>
          <span className="assistant-scope">IT support⌄</span>
        </header>
        <div className="message-list" aria-live="polite">
          {messageCursor ? (
            <button
              className="load-more-button message-history-button"
              disabled={Boolean(loadingMore)}
              onClick={() => void loadOlderMessages()}
              type="button"
            >
              {loadingMore === "messages" ? "Đang tải…" : "Tải tin nhắn cũ hơn"}
            </button>
          ) : null}
          {messages.length === 0 ? (
            <div className="chat-empty">
              <strong>Bạn đang gặp vấn đề gì?</strong>
              <p>Hãy mô tả lỗi, thiết bị và thao tác bạn đã thử.</p>
            </div>
          ) : null}
          {messages.map((message) => (
            <article className={`chat-message ${message.role}`} key={message.id}>
              <span>{message.role === "user" ? "Bạn" : "IT Assistant"}</span>
              <SafeMarkdown content={message.content} />
              {message.citations?.length ? (
                <CitationList citations={message.citations} />
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
              onEdit={() => handleApprovalEdit(approval)}
            />
          ))}
        {notice ? <p className="notice-banner" role="status">{notice}</p> : null}
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
      <aside className="chat-context-rail">
        <section className="context-card">
          <header><div><span aria-hidden="true">▧</span><h2>Nguồn tham chiếu</h2></div><span>{contextSources.length}</span></header>
          {contextSources.length ? <ul>{contextSources.map((source) => <li key={source.source_id}><span className="context-item-icon" aria-hidden="true">▤</span><div><strong>{source.title}</strong><small>{source.page_number ? `Trang ${source.page_number}` : "Kho tri thức"}</small></div></li>)}</ul> : <p className="context-empty">Nguồn của câu trả lời gần nhất sẽ xuất hiện tại đây.</p>}
        </section>
        <section className="context-card">
          <header><div><span aria-hidden="true">▣</span><h2>Thao tác đang chờ</h2></div><span>{approvals.length}</span></header>
          {approvals.length ? <ul>{approvals.slice(0, 3).map((approval) => <li key={approval.id}><span className="context-item-icon amber" aria-hidden="true">!</span><div><strong>{approval.canonical_args.title}</strong><small>Chờ bạn xác nhận</small></div></li>)}</ul> : <p className="context-empty">Không có bản nháp cần xác nhận.</p>}
        </section>
        <section className="context-card context-tip">
          <header><div><span aria-hidden="true">⚡</span><h2>Gợi ý</h2></div></header>
          <p>Hãy nêu thiết bị, thông báo lỗi và thao tác bạn đã thử để nhận câu trả lời chính xác hơn.</p>
        </section>
      </aside>
    </div>
  );
}
