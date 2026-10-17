import assert from "node:assert/strict";
import { test } from "node:test";

import { createEventStreamParser } from "./sse.js";

test("parses named events with JSON payloads", () => {
  const parser = createEventStreamParser();

  assert.deepEqual(parser.push('event: status\ndata: {"stage":"planning"}\n\n'), [
    { event: "status", data: '{"stage":"planning"}' },
  ]);
});

test("reassembles an event split across chunks", () => {
  const parser = createEventStreamParser();

  assert.deepEqual(parser.push("event: token\nda"), []);
  assert.deepEqual(parser.push('ta: {"text":"hi"}\n'), []);
  assert.deepEqual(parser.push("\n"), [{ event: "token", data: '{"text":"hi"}' }]);
});

test("parses several events from a single chunk", () => {
  const parser = createEventStreamParser();

  const events = parser.push(
    'event: message_start\ndata: {"conversationId":"c1"}\n\n' +
      'event: status\ndata: {"stage":"classifying"}\n\n',
  );

  assert.deepEqual(events, [
    { event: "message_start", data: '{"conversationId":"c1"}' },
    { event: "status", data: '{"stage":"classifying"}' },
  ]);
});

test("ignores comments and unknown fields", () => {
  const parser = createEventStreamParser();

  assert.deepEqual(parser.push(': keep-alive\nid: 7\nevent: token\ndata: {"text":"ok"}\n\n'), [
    { event: "token", data: '{"text":"ok"}' },
  ]);
});

test("joins multi-line data with newlines", () => {
  const parser = createEventStreamParser();

  assert.deepEqual(parser.push("event: token\ndata: first\ndata: second\n\n"), [
    { event: "token", data: "first\nsecond" },
  ]);
});

test("tolerates CRLF line endings", () => {
  const parser = createEventStreamParser();

  assert.deepEqual(parser.push('event: status\r\ndata: {"stage":"composing"}\r\n\r\n'), [
    { event: "status", data: '{"stage":"composing"}' },
  ]);
});

test("flush emits a trailing event without a blank line", () => {
  const parser = createEventStreamParser();

  assert.deepEqual(parser.push('event: token\ndata: {"text":"done"}'), []);
  assert.deepEqual(parser.flush(), [{ event: "token", data: '{"text":"done"}' }]);
});

test("drops blocks that carry no data", () => {
  const parser = createEventStreamParser();

  assert.deepEqual(parser.push("event: ping\n\n"), []);
  assert.deepEqual(parser.flush(), []);
});
