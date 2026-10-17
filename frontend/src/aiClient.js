// Client for the read-only assistant (the `expense-ai` service).
//
// The browser always talks to the assistant through this app's own origin: Vite
// proxies `/ai` in development and nginx does the same in staging. Keeping the
// call same-origin means the existing bearer token is reused without opening a
// second CORS surface.
//
// Chat responses are `text/event-stream`, so they are read with `fetch` plus a
// stream reader. `EventSource` cannot attach an Authorization header.

import { createEventStreamParser } from "./sse";

export const AI_BASE = "/ai";

const STATUS_FALLBACKS = {
  401: "Your session expired. Please log in again.",
  403: "You do not have access to the assistant.",
  404: "That conversation no longer exists.",
  413: "That message is too long.",
  422: "That message is too long.",
  429: "You are sending messages too quickly. Please wait a moment.",
  503: "The assistant is temporarily unavailable. Please try again.",
  504: "The assistant timed out while answering. Please try again.",
};

function authorizationHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function extractErrorMessage(response) {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    try {
      const body = await response.json();
      const detail = Array.isArray(body.detail)
        ? body.detail.map((item) => item?.msg).filter(Boolean).join(", ")
        : body.detail;
      const message = body.message || body.error || detail;
      if (message) {
        return String(message);
      }
    } catch {
      // A malformed body is not worth surfacing; fall back to the status message.
    }
  }

  return STATUS_FALLBACKS[response.status] || `The assistant request failed (${response.status}).`;
}

function buildError(message, status) {
  const error = new Error(message);
  error.status = status;
  return error;
}

async function aiRequest(path, { method = "GET", token, signal } = {}) {
  const response = await fetch(`${AI_BASE}${path}`, {
    method,
    headers: authorizationHeaders(token),
    signal,
  });

  if (!response.ok) {
    throw buildError(await extractErrorMessage(response), response.status);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export function listConversations(token, signal) {
  return aiRequest("/conversations", { token, signal });
}

export function getConversation(token, conversationId, signal) {
  return aiRequest(`/conversations/${encodeURIComponent(conversationId)}`, { token, signal });
}

export function deleteConversation(token, conversationId) {
  return aiRequest(`/conversations/${encodeURIComponent(conversationId)}`, {
    method: "DELETE",
    token,
  });
}

// Streams one turn, invoking `onEvent(eventName, payload)` for each typed event.
// Resolves when the stream ends; rejects with `status` set for HTTP failures and
// with an `AbortError` when the caller cancels.
export async function streamChat({ token, message, conversationId, signal, onEvent }) {
  let response;
  try {
    response = await fetch(`${AI_BASE}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...authorizationHeaders(token),
      },
      body: JSON.stringify({ message, conversation_id: conversationId || null }),
      signal,
    });
  } catch (caught) {
    if (caught.name === "AbortError") {
      throw caught;
    }
    throw buildError("Could not reach the assistant. Please check your connection and try again.", 0);
  }

  if (!response.ok) {
    throw buildError(await extractErrorMessage(response), response.status);
  }

  if (!response.body) {
    throw buildError("The assistant returned an empty response.", response.status);
  }

  const parser = createEventStreamParser();
  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  function dispatch(raw) {
    let payload = {};
    if (raw.data) {
      try {
        payload = JSON.parse(raw.data);
      } catch {
        payload = { text: raw.data };
      }
    }
    onEvent(raw.event, payload);
  }

  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      for (const raw of parser.push(decoder.decode(value, { stream: true }))) {
        dispatch(raw);
      }
    }
    for (const raw of parser.flush()) {
      dispatch(raw);
    }
  } finally {
    reader.releaseLock();
  }
}
