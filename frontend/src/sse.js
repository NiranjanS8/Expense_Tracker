// Incremental parser for the `text/event-stream` responses the assistant sends.
//
// Network chunks do not respect event boundaries, so callers feed the parser raw
// decoded text and receive whole events back. The parser is deliberately free of
// browser APIs so it can be exercised directly by Node's test runner.

const DATA_SEPARATOR = "\n\n";

function parseBlock(block) {
  let event = "message";
  const dataLines = [];

  for (const line of block.split("\n")) {
    if (line === "" || line.startsWith(":")) {
      continue;
    }

    const separator = line.indexOf(":");
    const field = separator === -1 ? line : line.slice(0, separator);
    let value = separator === -1 ? "" : line.slice(separator + 1);
    if (value.startsWith(" ")) {
      value = value.slice(1);
    }

    if (field === "event") {
      event = value;
    } else if (field === "data") {
      dataLines.push(value);
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  return { event, data: dataLines.join("\n") };
}

export function createEventStreamParser() {
  let buffer = "";

  return {
    push(chunk) {
      buffer += String(chunk).replace(/\r\n/g, "\n");

      const events = [];
      let separator = buffer.indexOf(DATA_SEPARATOR);
      while (separator !== -1) {
        const parsed = parseBlock(buffer.slice(0, separator));
        buffer = buffer.slice(separator + DATA_SEPARATOR.length);
        if (parsed) {
          events.push(parsed);
        }
        separator = buffer.indexOf(DATA_SEPARATOR);
      }

      return events;
    },

    // A well-behaved server terminates every event with a blank line. Calling
    // flush() at end-of-stream keeps a truncated final event from being lost.
    flush() {
      const parsed = parseBlock(buffer);
      buffer = "";
      return parsed ? [parsed] : [];
    },
  };
}
