"use client";

import { useState, useEffect, useRef, FormEvent } from "react";
import Link from "next/link";
import { JJK, glowColor } from "@/lib/jjk-theme";
import NomadStatusWidget from "@/components/NomadStatusWidget";
import RagChatBar from "@/components/RagChatBar";

interface Message {
  role: "user" | "assistant";
  content: string;
  provider?: string;
  feedback?: "up" | "down" | null;
  timestamp: number;
  sources?: Array<{
    id: string;
    score: number;
    text: string;
  }>;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState<string>("unknown");
  const [connected, setConnected] = useState(true);
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const saved = localStorage.getItem("aura-chat-history");
    if (saved) {
      try {
        setMessages(JSON.parse(saved));
      } catch {
        setMessages([]);
      }
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("aura-chat-history", JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { role: "user", content: input.trim(), timestamp: Date.now() };
    const assistantMessage: Message = { role: "assistant", content: "", timestamp: Date.now() };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput("");
    setIsLoading(true);
    setError(null);
    setProvider("unknown");

    try {
      const formData = new FormData();
      formData.append("prompt", userMessage.content);
      formData.append("router", "true");
      const storySessionId = localStorage.getItem("aura-chat-session-id");
      if (storySessionId) {
        formData.append("session_id", storySessionId);
      }
      if (selectedImage) {
        formData.append("image", selectedImage);
      }
      if (selectedFile) {
        formData.append("file", selectedFile);
      }

      const res = await fetch("/api/ame-core", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.text();
        throw new Error(err || `Error ${res.status}`);
      }

      const data = await res.json();
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          content: data.result || data.text || "",
          provider: data.provider || "unknown",
        };
        return updated;
      });
      setProvider(data.provider || "unknown");
      setSelectedImage(null);
      setImagePreview(null);
      setSelectedFile(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error desconocido";
      setError(msg);
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          content: `Error: ${msg}`,
        };
        return updated;
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleFeedback = async (messageIndex: number, value: "up" | "down") => {
    const msg = messages[messageIndex];
    if (!msg || msg.role !== "assistant") return;

    setMessages((prev) => {
      const updated = [...prev];
      updated[messageIndex] = { ...updated[messageIndex], feedback: value };
      return updated;
    });

    try {
      await fetch("/api/ame-core", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: messages[messageIndex - 1]?.content || "", feedback: value }),
      });
    } catch {
      // noop
    }
  };

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedImage(file);
      const reader = new FileReader();
      reader.onload = () => setImagePreview(reader.result as string);
      reader.readAsDataURL(file);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) setSelectedFile(file);
  };

  const clearHistory = () => {
    setMessages([]);
    localStorage.removeItem("aura-chat-history");
  };

  return (
    <div
      className="flex flex-col h-screen"
      style={{
        backgroundColor: JJK.BG,
        color: JJK.TEXT,
        fontFamily: "'JetBrains Mono', 'Courier New', monospace",
      }}
    >
      <header
        className="flex items-center justify-between p-4 border-b"
        style={{
          backgroundColor: JJK.PANEL,
          borderColor: `${JJK.ACCENT}44`,
          boxShadow: `0 0 15px ${glowColor(JJK.ACCENT, 0.2)}`,
        }}
      >
        <div>
          <h1 className="text-xl font-bold" style={{ color: JJK.ACCENT2, textShadow: `0 0 10px ${glowColor(JJK.ACCENT2, 0.5)}` }}>
            AURA Chat
          </h1>
          <div className="flex items-center gap-2 text-sm" style={{ color: "#aaa" }}>
            <span className={`w-2 h-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`} />
            <span>{connected ? "Conectado" : "Desconectado"}</span>
            <span>|</span>
            <span>Proveedor: {provider}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <Link
            href="/gesture-control"
            className="px-3 py-1 text-sm rounded"
            style={{
              border: `1px solid ${JJK.ACCENT}`,
              color: JJK.TEXT,
              background: `${JJK.ACCENT}22`,
              textDecoration: "none",
            }}
          >
            🎬 Gestos
          </Link>
          <button
            onClick={clearHistory}
            className="px-3 py-1 text-sm rounded"
            style={{
              border: `1px solid ${JJK.RED}44`,
              color: JJK.TEXT,
              background: `${JJK.RED}22`,
            }}
          >
            Limpiar chat
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-hidden">
        <div className="h-full flex">
          <div className="flex-1 flex flex-col">
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 && (
                <p className="text-gray-400 text-center mt-10">
                  Inicia una conversación con AURA...
                </p>
              )}
              {messages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    className="max-w-lg rounded-lg px-4 py-2 shadow"
                    style={
                      msg.role === "user"
                        ? {
                            backgroundColor: JJK.ACCENT,
                            color: "#fff",
                            boxShadow: `0 0 15px ${glowColor(JJK.ACCENT, 0.4)}`,
                          }
                        : {
                            backgroundColor: JJK.PANEL,
                            color: JJK.TEXT,
                            border: `1px solid ${JJK.ACCENT}22`,
                            boxShadow: `0 0 15px ${glowColor(JJK.ACCENT, 0.1)}`,
                          }
                    }
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {msg.sources.map((src, i) => (
                          <span
                            key={i}
                            title={`score: ${src.score.toFixed(2)}`}
                            style={{
                              fontSize: 10,
                              color: "#9ad7ff",
                              background: "rgba(0,240,255,0.08)",
                              border: "1px solid rgba(0,240,255,0.18)",
                              borderRadius: 999,
                              padding: "3px 8px",
                            }}
                          >
                            FUENTE {i + 1}
                          </span>
                        ))}
                      </div>
                    )}
                    {msg.role === "assistant" && msg.content && (
                      <div className="flex items-center gap-2 mt-2">
                        <span className="text-xs text-gray-400">{msg.provider}</span>
                        <button onClick={() => handleFeedback(idx, "up")} className="text-sm hover:scale-110 transition">👍</button>
                        <button onClick={() => handleFeedback(idx, "down")} className="text-sm hover:scale-110 transition">👎</button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex justify-start">
                  <div className="bg-gray-700 text-gray-100 rounded-lg px-4 py-2 shadow animate-pulse">
                    Escribiendo...
                  </div>
                </div>
              )}
              {error && (
                <div className="bg-red-800 text-white p-3 rounded-lg text-center">{error}</div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {imagePreview && (
              <div className="px-4 pb-2">
                <div className="relative inline-block">
                  <img src={imagePreview} alt="preview" className="h-20 rounded border border-gray-600" />
                  <button onClick={() => { setSelectedImage(null); setImagePreview(null); }} className="absolute -top-2 -right-2 bg-red-600 text-white rounded-full w-5 h-5 text-xs">×</button>
                </div>
              </div>
            )}

            <RagChatBar
              onInsert={(text, sources) => {
                const userMessage: Message = {
                  role: "user",
                  content: `[RAG QUERY] ${text}`,
                  timestamp: Date.now(),
                };
                const assistantMessage: Message = {
                  role: "assistant",
                  content: text,
                  timestamp: Date.now(),
                  sources,
                };
                setMessages((prev) => [...prev, userMessage, assistantMessage]);
              }}
            />

            <form
              onSubmit={handleSubmit}
              className="p-4 border-t"
              style={{ backgroundColor: JJK.PANEL, borderColor: `${JJK.ACCENT}44` }}
            >
              <div className="flex items-center gap-2">
                <input type="file" ref={imageInputRef} onChange={handleImageChange} accept="image/*" className="hidden" />
                <input type="file" ref={fileInputRef} onChange={handleFileChange} className="hidden" />
                <button type="button" onClick={() => imageInputRef.current?.click()} className="p-2 rounded" style={{ border: `1px solid ${JJK.ACCENT}44`, background: `${JJK.ACCENT}11` }}>🖼️</button>
                <button type="button" onClick={() => fileInputRef.current?.click()} className="p-2 rounded" style={{ border: `1px solid ${JJK.ACCENT}44`, background: `${JJK.ACCENT}11` }}>📎</button>
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Escribe tu mensaje..."
                  className="flex-1 p-3 rounded-lg border focus:outline-none"
                  style={{
                    backgroundColor: JJK.BG,
                    color: JJK.TEXT,
                    borderColor: `${JJK.ACCENT}33`,
                  }}
                  disabled={isLoading}
                />
                <button
                  type="submit"
                  disabled={isLoading}
                  className="text-white font-bold py-3 px-6 rounded-lg shadow-md transition disabled:opacity-50"
                  style={{
                    backgroundColor: JJK.ACCENT,
                    boxShadow: `0 0 15px ${glowColor(JJK.ACCENT, 0.5)}`,
                  }}
                >
                  {isLoading ? "..." : "⚡ Enviar"}
                </button>
              </div>
            </form>
          </div>

          <div className="w-64 border-l p-3 space-y-4 overflow-y-auto" style={{ borderColor: `${JJK.ACCENT}22`, background: "rgba(5,10,15,0.6)" }}>
            <NomadStatusWidget />
          </div>
        </div>
      </div>
    </div>
  );
}
