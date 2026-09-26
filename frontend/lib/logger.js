const MAX_LOGS = 500;
const buffer = [];

function emit(entry) {
  const meta = entry.meta ? ` ${JSON.stringify(entry.meta)}` : "";
  const line = `[${entry.ts}] ${entry.level.toUpperCase()} [${entry.category}] ${entry.message}${meta}`;
  if (entry.level === "error") console.error(line);
  else console.log(line);
}

function add(level, category, message, meta) {
  const entry = {
    ts: new Date().toISOString(),
    level,
    category,
    message,
    meta: meta === undefined ? null : meta,
  };
  buffer.push(entry);
  if (buffer.length > MAX_LOGS) buffer.shift();
  emit(entry);
  return entry;
}

const logger = {
  info(category, message, meta) {
    return add("info", category, message, meta);
  },
  warn(category, message, meta) {
    return add("warn", category, message, meta);
  },
  error(category, message, err) {
    const meta =
      err && typeof err === "object"
        ? { message: err.message, stack: err.stack }
        : { value: err };
    return add("error", category, message, meta);
  },
  event(message, meta) {
    return add("info", "integration", message, meta);
  },
  api(method, path, ms, status) {
    return add("info", "api", `${method} ${path}`, { ms, status });
  },
  getLogs(limit) {
    return limit ? buffer.slice(-limit) : buffer.slice();
  },
  clear() {
    buffer.length = 0;
  },
};

module.exports = logger;
