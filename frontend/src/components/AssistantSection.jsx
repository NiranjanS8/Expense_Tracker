import { useCallback, useEffect, useRef, useState } from "react";
import { ClipboardList, MessageSquarePlus, Send, Sparkles, Square, Trash2 } from "lucide-react";

import {
  deleteConversation,
  getConversation,
  listConversations,
  streamChat,
} from "../aiClient";
import { draftFormLabel } from "../drafts";

const MAX_MESSAGE_LENGTH = 4000;

const STATUS_LABELS = {
  classifying: "Understanding your question",
  planning: "Working out how to answer",
  validating: "Checking the request",
  authorizing: "Checking permissions",
  retrieving: "Retrieving your data",
  verifying: "Verifying the data",
  drafting: "Preparing a draft",
  composing: "Writing the answer",
};

const TERMINATION_NOTES = {
  no_data: "No matching data was found.",
  tool_error: "A dependent service was unavailable for this answer.",
  model_error: "The assistant could not compose an answer.",
};

const TOOL_LABELS = {
  get_spending_summary: "spending summary",
  search_expenses: "expense search",
  get_category_breakdown: "category breakdown",
  get_dashboard_summary: "dashboard summary",
  get_budget_status: "budget status",
  get_goal_progress: "goal progress",
  get_recurring_expenses: "recurring expenses",
  get_existing_insights: "existing insights",
};

function toolLabel(name) {
  return TOOL_LABELS[name] || String(name).replace(/_/g, " ");
}

function formatTimestamp(value) {
  if (!value) {
    return "";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export default function AssistantSection({ token, onUnauthorized, onApplyDraft }) {
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [statusStage, setStatusStage] = useState("");
  const [statusTool, setStatusTool] = useState("");
  const [error, setError] = useState("");
  const [loadingConversation, setLoadingConversation] = useState(false);

  const abortRef = useRef(null);
  const threadRef = useRef(null);
  const unauthorizedRef = useRef(onUnauthorized);

  useEffect(() => {
    unauthorizedRef.current = onUnauthorized;
  }, [onUnauthorized]);

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await listConversations(token));
    } catch (caught) {
      if (caught.status === 401) {
        unauthorizedRef.current();
        return;
      }
      setError(caught.message);
    }
  }, [token]);

  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  useEffect(() => {
    const thread = threadRef.current;
    if (thread) {
      thread.scrollTop = thread.scrollHeight;
    }
  }, [messages, statusStage]);

  useEffect(() => () => abortRef.current?.abort(), []);

  function updateLastAssistant(update) {
    setMessages((current) => {
      const last = current[current.length - 1];
      if (!last || last.role !== "assistant") {
        return current;
      }
      const next = [...current];
      next[next.length - 1] = update(last);
      return next;
    });
  }

  function appendToAssistant(text) {
    updateLastAssistant((last) => ({ ...last, content: `${last.content}${text}` }));
  }

  function attachDraft(payload) {
    updateLastAssistant((last) => ({ ...last, draft: payload }));
  }

  function clearEmptyAssistant() {
    setMessages((current) => {
      const last = current[current.length - 1];
      if (!last || last.role !== "assistant") {
        return current;
      }
      if (!last.content) {
        return current.slice(0, -1);
      }
      return [...current.slice(0, -1), { ...last, streaming: false }];
    });
  }

  function finalizeAssistant(payload) {
    updateLastAssistant((last) => ({
      ...last,
      content: payload.content ?? last.content,
      toolCalls: Array.isArray(payload.toolCalls) ? payload.toolCalls : [],
      termination: payload.termination || "",
      streaming: false,
    }));
    if (payload.conversationId) {
      setConversationId(payload.conversationId);
    }
  }

  function startNewConversation() {
    if (streaming) {
      return;
    }
    setConversationId(null);
    setMessages([]);
    setError("");
    setStatusStage("");
    setStatusTool("");
  }

  async function selectConversation(id) {
    if (streaming) {
      return;
    }

    setError("");
    setConversationId(id);
    setMessages([]);
    setLoadingConversation(true);

    try {
      const detail = await getConversation(token, id);
      setMessages(
        detail.messages.map((message) => ({
          id: message.id,
          role: message.role,
          content: message.content,
          toolCalls: [],
          termination: "",
        })),
      );
    } catch (caught) {
      if (caught.status === 401) {
        unauthorizedRef.current();
        return;
      }
      setError(caught.message);
      setConversationId(null);
      await refreshConversations();
    } finally {
      setLoadingConversation(false);
    }
  }

  async function removeConversation(id) {
    if (streaming) {
      return;
    }

    setError("");
    try {
      await deleteConversation(token, id);
      if (id === conversationId) {
        setConversationId(null);
        setMessages([]);
      }
      await refreshConversations();
    } catch (caught) {
      if (caught.status === 401) {
        unauthorizedRef.current();
        return;
      }
      setError(caught.message);
    }
  }

  function stopStreaming() {
    abortRef.current?.abort();
  }

  async function submitMessage(event) {
    event.preventDefault();

    const message = draft.trim();
    if (!message || streaming) {
      return;
    }

    setError("");
    setDraft("");
    setStatusStage("classifying");
    setStatusTool("");
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    setMessages((current) => [
      ...current,
      { role: "user", content: message, toolCalls: [], termination: "" },
      { role: "assistant", content: "", toolCalls: [], termination: "", streaming: true },
    ]);

    try {
      await streamChat({
        token,
        message,
        conversationId,
        signal: controller.signal,
        onEvent: (name, payload) => {
          if (name === "message_start") {
            if (payload.conversationId) {
              setConversationId(payload.conversationId);
            }
            return;
          }
          if (name === "status") {
            setStatusStage(payload.stage || "");
            setStatusTool(payload.tool || "");
            return;
          }
          if (name === "token") {
            appendToAssistant(payload.text || "");
            return;
          }
          if (name === "draft") {
            attachDraft(payload);
            return;
          }
          if (name === "message_complete") {
            finalizeAssistant(payload);
            return;
          }
          if (name === "error") {
            setError(payload.message || "The assistant could not answer that question.");
            clearEmptyAssistant();
          }
        },
      });
    } catch (caught) {
      if (caught.name === "AbortError") {
        clearEmptyAssistant();
      } else if (caught.status === 401) {
        unauthorizedRef.current();
      } else {
        setError(caught.message);
        clearEmptyAssistant();
      }
    } finally {
      abortRef.current = null;
      setStreaming(false);
      setStatusStage("");
      setStatusTool("");
      await refreshConversations();
    }
  }

  function handleComposerKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitMessage(event);
    }
  }

  const statusLabel =
    statusStage === "retrieving" && statusTool
      ? `Retrieving ${toolLabel(statusTool)}`
      : STATUS_LABELS[statusStage] || "Working";

  return (
    <div className="chat-layout">
      <aside className="glass-panel chat-sidebar">
        <div className="chat-sidebar__head">
          <span className="eyebrow">Conversations</span>
          <button
            className="ghost-button icon-only"
            type="button"
            title="New chat"
            aria-label="New chat"
            onClick={startNewConversation}
            disabled={streaming}
          >
            <MessageSquarePlus size={16} />
          </button>
        </div>

        {conversations.length === 0 ? (
          <p className="muted">No conversations yet. Your chats will appear here.</p>
        ) : (
          <div className="chat-conversations">
            {conversations.map((conversation) => (
              <div
                key={conversation.id}
                className={`chat-conversation ${conversation.id === conversationId ? "is-active" : ""}`}
              >
                <button
                  className="chat-conversation__main"
                  type="button"
                  onClick={() => void selectConversation(conversation.id)}
                  disabled={streaming}
                >
                  <strong>{conversation.title || "Untitled conversation"}</strong>
                  <span className="muted">{formatTimestamp(conversation.updatedAt)}</span>
                </button>
                <button
                  className="text-button text-button--danger"
                  type="button"
                  title="Delete conversation"
                  aria-label={`Delete ${conversation.title || "conversation"}`}
                  onClick={() => void removeConversation(conversation.id)}
                  disabled={streaming}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </aside>

      <section className="glass-panel chat-panel">
        <header className="chat-panel__head">
          <div>
            <span className="eyebrow">Assistant</span>
            <h2>Ask about your money</h2>
          </div>
          <p className="muted">
            Read-only: answers come from your own Expense Tracker data and nothing is ever changed.
            I can draft an entry for you, but you save it yourself.
          </p>
        </header>

        <div className="chat-thread" ref={threadRef}>
          {loadingConversation && <p className="muted">Loading conversation…</p>}

          {!loadingConversation && messages.length === 0 && (
            <div className="chat-empty">
              <Sparkles size={22} />
              <p className="chat-empty__lead">Ask a question about your spending.</p>
              <ul className="chat-empty__examples">
                <li>How much did I spend this month?</li>
                <li>How is my food budget tracking?</li>
                <li>What were my biggest expenses last week?</li>
                <li>Am I on track for my savings goal?</li>
                <li>Add a 12.50 coffee expense yesterday</li>
              </ul>
            </div>
          )}

          {messages.map((message, index) => {
            const note = TERMINATION_NOTES[message.termination];
            const tools = message.toolCalls || [];
            return (
              <article key={`${message.role}-${message.id ?? index}`} className={`chat-message chat-message--${message.role}`}>
                <div className="chat-message__bubble">
                  {message.content || (message.streaming && <span className="muted">…</span>)}
                </div>
                {(tools.length > 0 || note) && (
                  <div className="chat-message__meta">
                    {tools.map((name, toolIndex) => (
                      <span className="chat-tool-chip" key={`${name}-${toolIndex}`}>
                        {toolLabel(name)}
                      </span>
                    ))}
                    {note && <span className="chat-note">{note}</span>}
                  </div>
                )}
                {message.draft && (
                  <div className="chat-draft">
                    <p className="chat-draft__summary">{message.draft.summary}</p>
                    <button
                      className="ghost-button"
                      type="button"
                      onClick={() => onApplyDraft?.(message.draft)}
                    >
                      <ClipboardList size={14} />
                      Review in the {draftFormLabel(message.draft)}
                    </button>
                    <span className="muted chat-draft__note">
                      Nothing is saved until you press Save.
                    </span>
                  </div>
                )}
              </article>
            );
          })}

          {streaming && (
            <div className="chat-status">
              <span className="chat-status__dots" aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
              {statusLabel}
            </div>
          )}
        </div>

        {error && <p className="form-error chat-panel__error">{error}</p>}

        <form className="chat-composer" onSubmit={submitMessage}>
          <textarea
            aria-label="Message the assistant"
            rows={3}
            maxLength={MAX_MESSAGE_LENGTH}
            placeholder="Ask about your spending, budgets, goals or insights…"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleComposerKeyDown}
            disabled={streaming}
          />
          <div className="chat-composer__row">
            <span className="muted">
              {draft.length}/{MAX_MESSAGE_LENGTH} · Enter to send, Shift+Enter for a new line
            </span>
            {streaming ? (
              <button className="ghost-button" type="button" onClick={stopStreaming}>
                <Square size={14} />
                Stop
              </button>
            ) : (
              <button className="primary-button" type="submit" disabled={!draft.trim()}>
                <Send size={16} />
                Send
              </button>
            )}
          </div>
        </form>
      </section>
    </div>
  );
}
