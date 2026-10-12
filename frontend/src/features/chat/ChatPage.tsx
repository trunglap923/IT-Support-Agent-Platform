import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  ChevronDown,
  Check,
  ClipboardCheck,
  Copy,
  FileText,
  Laptop,
  Lightbulb,
  MessageCircle,
  MessagesSquare,
  Plus,
  PlusCircle,
  Search,
  Send,
  Sparkles,
  TicketCheck,
  ThumbsDown,
  ThumbsUp,
  TicketPlus,
  X,
} from "lucide-react";
import { Link } from "react-router-dom";

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
import { LoadingState, StatusBadge } from "../../components/ProductUI";
import { listMemoryDevices, type MemoryDevice } from "../../api/memory";
import { listMyTickets, type Ticket } from "../../api/tickets";
import { formatIssueType, formatRelativeTime, formatStatus } from "../../utils/format";
import { ApprovalCard } from "../tickets/ApprovalCard";
import { formatTicketDraftForChat } from "../tickets/approvalEdit";
import { CitationList } from "./CitationList";
import { recoverActiveRun } from "./chatRecovery";
import { CompletedRunProgress, RunStatusPanel, type RunProgressSummary } from "./RunStatusPanel";
import { SafeMarkdown } from "./SafeMarkdown";
import {
  conversationActivityAt,
  formatChatTime,
  formatConversationDate,
  groupConversationDate,
} from "./chatPresentation";

const devicePlatformLabels: Record<MemoryDevice["platform"], string> = {
  windows: "Windows",
  macos: "macOS",
  linux: "Linux",
  other: "Khác",
};

export function ChatPage() {
  const { csrfToken, user } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [active, setActive] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [draft, setDraft] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [completedProgress, setCompletedProgress] = useState<RunProgressSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [streamingAnswer, setStreamingAnswer] = useState("");
  const [feedbackPending, setFeedbackPending] = useState<string | null>(null);
  const [copiedMessage, setCopiedMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [conversationCursor, setConversationCursor] = useState<string | null>(null);
  const [messageCursor, setMessageCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState<"conversations" | "messages" | null>(null);
  const [conversationQuery, setConversationQuery] = useState("");
  const [conversationListOpen, setConversationListOpen] = useState(false);
  const [contextOpen, setContextOpen] = useState(() =>
    typeof window.matchMedia !== "function" || window.matchMedia("(min-width: 1101px)").matches,
  );
  const [devices, setDevices] = useState<MemoryDevice[]>([]);
  const [recentTickets, setRecentTickets] = useState<Ticket[]>([]);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const conversationToggleRef = useRef<HTMLButtonElement>(null);
  const conversationListRef = useRef<HTMLElement>(null);
  const pendingMessageRequest = useRef<ClientRequestIdentity | null>(null);
  const terminalRunIds = useRef(new Set<string>());

  const visibleConversations = useMemo(() => conversations
    .filter((conversation) => `${conversation.title} ${conversation.preview ?? ""}`
      .toLocaleLowerCase()
      .includes(conversationQuery.trim().toLocaleLowerCase()))
    .sort((left, right) => new Date(conversationActivityAt(right)).getTime() - new Date(conversationActivityAt(left)).getTime()),
  [conversationQuery, conversations]);
  const conversationGroups = useMemo(() => {
    const groups = new Map<string, Conversation[]>();
    for (const conversation of visibleConversations) {
      const group = groupConversationDate(conversationActivityAt(conversation));
      groups.set(group, [...(groups.get(group) ?? []), conversation]);
    }
    return [...groups.entries()];
  }, [visibleConversations]);
  const topicContext = `${active?.title ?? ""} ${messages.map((message) => message.content).join(" ")}`.toLocaleLowerCase();
  const quickActions = topicContext.includes("vpn")
    ? ["Kiểm tra trạng thái dịch vụ VPN", "Hướng dẫn khắc phục lỗi VPN", "Tạo ticket hỗ trợ"]
    : topicContext.includes("docker") || topicContext.includes("registry")
      ? ["Hướng dẫn kiểm tra Docker/registry", "Kiểm tra lỗi Docker gần nhất", "Tạo ticket hỗ trợ"]
      : topicContext.includes("gitlab")
        ? ["Hướng dẫn xử lý truy cập GitLab", "Kiểm tra quyền truy cập GitLab", "Tạo ticket hỗ trợ"]
        : ["Tóm tắt hướng xử lý", "Hỏi thêm về sự cố này", "Tạo ticket hỗ trợ"];
  const relatedDevice = devices.find((device) => device.id === active?.device_id) ?? devices[0];
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
    const lastMessage = messagePage.items.at(-1);
    if (lastMessage) {
      const preview = lastMessage.content.replace(/\s+/g, " ").slice(0, 180);
      setConversations((current) => current.map((conversation) => conversation.id === conversationId
        ? { ...conversation, preview, preview_at: lastMessage.created_at, preview_role: lastMessage.role, updated_at: lastMessage.created_at }
        : conversation));
      setActive((current) => current?.id === conversationId
        ? { ...current, preview, preview_at: lastMessage.created_at, preview_role: lastMessage.role, updated_at: lastMessage.created_at }
        : current);
    }
    setMessageCursor(messagePage.next_cursor);
    setApprovals(approvalPage.items);
    setRunId(
      recoverActiveRun(messagePage.items, approvalPage.items, terminalRunIds.current),
    );
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
          setRunId(
            recoverActiveRun(messagePage.items, approvalPage.items, terminalRunIds.current),
          );
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

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(min-width: 1101px)");
    const syncContextVisibility = (event: MediaQueryListEvent) => setContextOpen(event.matches);
    media.addEventListener("change", syncContextVisibility);
    return () => media.removeEventListener("change", syncContextVisibility);
  }, []);

  useEffect(() => {
    if (!conversationListOpen) return;
    conversationListRef.current?.querySelector<HTMLButtonElement>(".conversation-close-button")?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setConversationListOpen(false);
      conversationToggleRef.current?.focus();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [conversationListOpen]);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      listMemoryDevices(controller.signal),
      listMyTickets(controller.signal),
    ]).then(([nextDevices, tickets]) => {
      setDevices(nextDevices.filter((device) => device.active).slice(0, 2));
      setRecentTickets(tickets.slice(0, 3));
    }).catch((caught: unknown) => {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) {
        // Context is supplementary; the main chat should remain available.
      }
    });
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
      setCompletedProgress(null);
      setStreamingAnswer("");
      setConversationListOpen(false);
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
    setCompletedProgress(null);
    setStreamingAnswer("");
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
      setStreamingAnswer("");
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

  const handleRunTerminal = useCallback((status: string) => {
    if (runId) terminalRunIds.current.add(runId);
    setRunId(null);
    if (status === "failed") {
      setStreamingAnswer("");
      setError("Trợ lý không thể xử lý yêu cầu. Vui lòng thử lại.");
    }
    if (status === "cancelled") setStreamingAnswer("");
    if (active) {
      void refreshConversation(active.id).finally(() => setStreamingAnswer(""));
    } else {
      setStreamingAnswer("");
    }
  }, [active, refreshConversation, runId]);

  const handleProgressComplete = useCallback((summary: RunProgressSummary) => {
    setCompletedProgress(summary);
  }, []);

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

  async function handleCopyAnswer(message: ChatMessage) {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopiedMessage(message.id);
      window.setTimeout(() => setCopiedMessage((current) => current === message.id ? null : current), 1800);
    } catch {
      setError("Không thể sao chép câu trả lời trên trình duyệt này.");
    }
  }

  function prepareTicketRequest(message: ChatMessage) {
    const messageIndex = messages.findIndex((item) => item.id === message.id);
    const latestUserMessage = messages.slice(0, messageIndex).reverse().find((item) => item.role === "user");
    const description = latestUserMessage?.content ?? active?.title ?? "Sự cố cần hỗ trợ";
    setDraft(`Tạo ticket hỗ trợ về sự cố: ${active?.title ?? "IT support"}\n\nMô tả lỗi: ${description}\n\nThông tin đã kiểm tra: ${message.content.slice(0, 900)}`);
    setNotice("Đã soạn yêu cầu tạo ticket. Kiểm tra nội dung rồi gửi để trợ lý tạo bản nháp chờ bạn xác nhận.");
    requestAnimationFrame(() => composerRef.current?.focus());
  }

  function applyQuickAction(action: string) {
    if (action === "Tạo ticket hỗ trợ") {
      const latestUserMessage = [...messages].reverse().find((message) => message.role === "user");
      setDraft(`Tạo ticket hỗ trợ cho vấn đề: ${active?.title ?? "IT support"}${latestUserMessage ? `\nMô tả: ${latestUserMessage.content}` : ""}`);
      setNotice("Đã soạn yêu cầu tạo ticket. Gửi tin nhắn để tạo bản nháp cần xác nhận.");
    } else {
      setDraft(action);
      setNotice(null);
    }
    requestAnimationFrame(() => composerRef.current?.focus());
  }

  if (loading) return <LoadingState label="Đang tải cuộc trò chuyện…" />;

  return (
    <div className="chat-layout">
      <aside
        aria-label="Hội thoại"
        className={conversationListOpen ? "conversation-list open" : "conversation-list"}
        id="conversation-list"
        ref={conversationListRef}
      >
        <div className="conversation-list-heading">
          <span>
            <strong>Hội thoại</strong>
            <small>{visibleConversations.length} cuộc trò chuyện</small>
          </span>
          <button
            aria-label="Đóng danh sách hội thoại"
            className="conversation-close-button"
            onClick={() => setConversationListOpen(false)}
            type="button"
          >
            <X aria-hidden="true" size={17} />
          </button>
        </div>
        <button className="new-chat-button" onClick={startConversation} type="button">
          <Plus aria-hidden="true" size={16} /> Cuộc trò chuyện mới
        </button>
        <label className="conversation-search"><Search aria-hidden="true" size={15} /><span className="sr-only">Tìm cuộc trò chuyện</span><input onChange={(event) => setConversationQuery(event.target.value)} placeholder="Tìm cuộc trò chuyện…" type="search" value={conversationQuery} /></label>
        <div aria-label="Danh sách cuộc trò chuyện" className="conversation-scroll" tabIndex={0}>
          {conversationGroups.map(([group, groupConversations]) => (
            <section className="conversation-group" key={group}>
              <p className="conversation-period">{group}</p>
              {groupConversations.map((conversation) => (
                <button
                  className={conversation.id === active?.id ? "active" : ""}
                  key={conversation.id}
                  onClick={() => {
                    setActive(conversation);
                    setCompletedProgress(null);
                    setStreamingAnswer("");
                    setConversationListOpen(false);
                    void refreshConversation(conversation.id);
                  }}
                  type="button"
                >
                  <MessageCircle aria-hidden="true" size={15} />
                  <span className="conversation-copy"><strong>{conversation.title}</strong><small>{conversation.preview_role === "assistant" ? "Trợ lý" : conversation.preview_role === "user" ? user?.display_name ?? "Bạn" : "Cuộc trò chuyện mới"}: {conversation.preview ?? "Bắt đầu cuộc trò chuyện"}</small></span>
                  <time dateTime={conversationActivityAt(conversation)}>{conversation.preview_at ? formatChatTime(conversation.preview_at) : formatConversationDate(conversation.updated_at)}</time>
                </button>
              ))}
            </section>
          ))}
          {conversationGroups.length === 0 ? (
            <p className="conversation-empty">Không tìm thấy cuộc trò chuyện phù hợp.</p>
          ) : null}
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
        </div>
      </aside>
      {conversationListOpen ? (
        <button
          aria-label="Đóng danh sách hội thoại"
          className="conversation-backdrop"
          onClick={() => setConversationListOpen(false)}
          type="button"
        />
      ) : null}
      <section className="chat-panel">
        <header className="chat-panel-header">
          <button
            aria-controls="conversation-list"
            aria-expanded={conversationListOpen}
            aria-label="Mở danh sách hội thoại"
            className="conversation-toggle-button"
            onClick={() => setConversationListOpen(true)}
            ref={conversationToggleRef}
            type="button"
          >
            <MessagesSquare aria-hidden="true" size={18} />
          </button>
          <span className="assistant-mark" aria-hidden="true"><Sparkles size={20} /></span>
          <div className="assistant-heading"><h1>Trợ lý AI</h1><p>Hỗ trợ dựa trên tài liệu nội bộ và ngữ cảnh vận hành</p></div>
          <span className="assistant-scope"><i /> IT support <ChevronDown aria-hidden="true" size={13} /></span>
        </header>
        <div aria-label="Nội dung cuộc trò chuyện" className="message-list" aria-live="polite" tabIndex={0}>
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
              <span className="chat-empty-mark" aria-hidden="true"><Sparkles size={22} /></span>
              <h2>Bạn cần hỗ trợ vấn đề gì?</h2>
              <p>Mô tả lỗi, thiết bị và thao tác đã thử để nhận hướng dẫn chính xác hơn.</p>
              <div className="chat-empty-actions">
                {quickActions.slice(0, 2).map((action) => (
                  <button key={action} onClick={() => applyQuickAction(action)} type="button">
                    {action}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {messages.map((message) => (
            <article className={`chat-message ${message.role}`} key={message.id}>
              <span className="message-avatar" aria-hidden="true">
                {message.role === "assistant" ? <Sparkles size={16} /> : user?.display_name?.slice(0, 1).toUpperCase() ?? "B"}
              </span>
              <div className="message-bubble">
                <header className="message-meta">
                  <strong>{message.role === "user" ? user?.display_name ?? "Bạn" : "Trợ lý AI"}</strong>
                  <time dateTime={message.created_at}>{formatChatTime(message.created_at)}</time>
                </header>
                <SafeMarkdown content={message.content} />
                {message.citations?.length ? (
                  <CitationList citations={message.citations} />
                ) : null}
                {message.role === "assistant" && completedProgress?.runId === message.run_id ? (
                  <CompletedRunProgress summary={completedProgress} />
                ) : null}
                {message.role === "assistant" ? (
                  <div className="message-actions" aria-label="Thao tác với câu trả lời">
                    <div className="message-primary-actions">
                      <button onClick={() => void handleCopyAnswer(message)} type="button">
                        {copiedMessage === message.id ? <Check aria-hidden="true" size={14} /> : <Copy aria-hidden="true" size={14} />}
                        {copiedMessage === message.id ? "Đã sao chép" : "Sao chép"}
                      </button>
                      <button onClick={() => prepareTicketRequest(message)} type="button"><TicketPlus aria-hidden="true" size={14} /> Tạo ticket</button>
                    </div>
                    <div className="message-feedback-actions">
                      <span>Hữu ích?</span>
                      <button
                        aria-label="Câu trả lời hữu ích"
                        aria-pressed={message.feedback?.rating === "helpful"}
                        disabled={feedbackPending === message.id}
                        onClick={() => void handleFeedback(message.id, "helpful")}
                        type="button"
                      >
                        <ThumbsUp aria-hidden="true" size={14} /><span>Hữu ích</span>
                      </button>
                      <button
                        aria-label="Câu trả lời chưa tốt"
                        aria-pressed={message.feedback?.rating === "unhelpful"}
                        disabled={feedbackPending === message.id}
                        onClick={() => void handleFeedback(message.id, "unhelpful")}
                        type="button"
                      >
                        <ThumbsDown aria-hidden="true" size={14} /><span>Chưa tốt</span>
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            </article>
          ))}
          {streamingAnswer ? (
            <article className="chat-message assistant streaming" aria-label="Câu trả lời đang được tạo">
              <span className="message-avatar" aria-hidden="true"><Sparkles size={16} /></span>
              <div className="message-bubble">
                <header className="message-meta"><strong>Trợ lý AI</strong><span>Đang trả lời…</span></header>
                <SafeMarkdown content={streamingAnswer} />
              </div>
            </article>
          ) : null}
          {runId ? (
            <RunStatusPanel
              runId={runId}
              onStatus={handleRunStatus}
              onStreamText={setStreamingAnswer}
              onTerminal={handleRunTerminal}
              onProgressComplete={handleProgressComplete}
            />
          ) : null}
        </div>
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
          <div className="composer-surface">
            <label className="sr-only" htmlFor="chat-input">Tin nhắn</label>
            <textarea
              disabled={sending || Boolean(runId)}
              id="chat-input"
              maxLength={4000}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder="Mô tả vấn đề, thông báo lỗi hoặc câu hỏi của bạn…"
              ref={composerRef}
              rows={2}
              value={draft}
            />
            <footer className="composer-footer">
              <span><kbd>Ctrl</kbd> + <kbd>Enter</kbd> để gửi · {draft.length}/4000</span>
              <button disabled={!draft.trim() || sending || Boolean(runId)} type="submit">
                <Send aria-hidden="true" size={17} />
                <span>{sending ? "Đang gửi…" : "Gửi"}</span>
              </button>
            </footer>
          </div>
          <p>Trợ lý AI có thể mắc sai sót. Hãy kiểm tra lại thông tin quan trọng.</p>
        </form>
      </section>
      <details
        aria-label="Ngữ cảnh hỗ trợ và ticket"
        className="chat-context-rail"
        onToggle={(event) => setContextOpen(event.currentTarget.open)}
        open={contextOpen}
      >
        <summary className="chat-context-summary">Ngữ cảnh hỗ trợ <ChevronDown aria-hidden="true" size={16} /></summary>
        <section className="context-card">
          <header><div><FileText aria-hidden="true" size={16} /><h2>Nguồn tham chiếu</h2></div><span>{contextSources.length}</span></header>
          {contextSources.length ? <ul>{contextSources.map((source) => <li key={source.source_id}><span className="context-item-icon" aria-hidden="true"><FileText size={15} /></span><div><strong>{source.title}</strong><small>{source.page_number ? `Trang ${source.page_number}` : "Kho tri thức"}</small></div></li>)}</ul> : <p className="context-empty">Nguồn của câu trả lời gần nhất sẽ xuất hiện tại đây.</p>}
        </section>
        <section className="context-card">
          <header><div><Laptop aria-hidden="true" size={16} /><h2>Thiết bị liên quan</h2></div><span>{devices.length}</span></header>
          {relatedDevice ? <div className="context-detail"><div className="context-device-heading"><span className="context-item-icon" aria-hidden="true"><Laptop size={16} /></span><strong>{relatedDevice.label}</strong><StatusBadge value={relatedDevice.active ? "active" : "inactive"} /></div><dl><div><dt>Người dùng</dt><dd>{user?.display_name ?? "Tài khoản hiện tại"}</dd></div><div><dt>Nền tảng</dt><dd>{devicePlatformLabels[relatedDevice.platform]}</dd></div><div><dt>Cập nhật</dt><dd>{formatRelativeTime(relatedDevice.updated_at)}</dd></div></dl></div> : <p className="context-empty">Chưa có thiết bị đang hoạt động.</p>}
        </section>
        <section className="context-card">
          <header><div><TicketCheck aria-hidden="true" size={16} /><h2>Ticket gần đây</h2></div><span>{recentTickets.length}</span></header>
          {recentTickets.length ? <ul>{recentTickets.map((ticket) => <li key={ticket.id}><span className="context-item-icon" aria-hidden="true"><TicketCheck size={15} /></span><div><Link className="context-ticket-link" to={`/tickets/${ticket.id}`}><strong>{ticket.display_key} · {ticket.title}</strong></Link><small>{formatIssueType(ticket.issue_type)} · Mức độ {formatStatus(ticket.severity)} · {formatRelativeTime(ticket.updated_at)}</small><StatusBadge value={ticket.status} /></div></li>)}</ul> : <p className="context-empty">Chưa có ticket gần đây.</p>}
        </section>
        <section className="context-card">
          <header><div><ClipboardCheck aria-hidden="true" size={16} /><h2>Thao tác đang chờ</h2></div><span>{approvals.length}</span></header>
          {approvals.length ? <ul>{approvals.slice(0, 3).map((approval) => <li key={approval.id}><span className="context-item-icon amber" aria-hidden="true"><ClipboardCheck size={15} /></span><div><strong>{approval.canonical_args.title}</strong><small>Chờ bạn xác nhận</small></div></li>)}</ul> : <p className="context-empty">Không có bản nháp cần xác nhận.</p>}
        </section>
        <section className="context-card context-tip">
          <header><div><Lightbulb aria-hidden="true" size={16} /><h2>Đề xuất hành động</h2></div></header>
          <div className="quick-actions">{quickActions.map((action) => <button key={action} onClick={() => applyQuickAction(action)} type="button"><PlusCircle aria-hidden="true" size={14} />{action}</button>)}</div>
          <p className="context-tip-copy">Hãy nêu thiết bị, thông báo lỗi và thao tác bạn đã thử để nhận câu trả lời chính xác hơn.</p>
        </section>
      </details>
    </div>
  );
}
