interface LogEntry {
  ts: string;
  level: string;
  category: string;
  message: string;
  meta: unknown;
}

declare const logger: {
  info: (category: string, message: string, meta?: unknown) => LogEntry;
  warn: (category: string, message: string, meta?: unknown) => LogEntry;
  error: (category: string, message: string, err?: unknown) => LogEntry;
  event: (message: string, meta?: unknown) => LogEntry;
  api: (
    method: string,
    path: string,
    ms: number,
    status: number,
  ) => LogEntry;
  getLogs: (limit?: number) => LogEntry[];
  clear: () => void;
};

export = logger;
