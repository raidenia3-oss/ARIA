import { motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import { sendChat, type ChatResult } from "../services/api";
import MessageItem, { MessageData } from "./MessageItem";

export default function ChatPanel({ persona, provider }: { persona: string; provider: string }) {
    const [messages, setMessages] = useState<MessageData[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const send = useCallback(async () => {
        const text = input.trim();
        if (!text) return;
        if (loading) return;

        const userMsg: MessageData = {
            id: `user-${Date.now()}`,
            role: "user",
            content: text,
        };
        setMessages((m) => [...m, userMsg]);
        setInput("");
        setLoading(true);

        const streamId = `stream-${Date.now()}`;
        setMessages((m) => [
            ...m,
            { id: streamId, role: "assistant", content: "", isStreaming: true },
        ]);

        try {
            const result: ChatResult = await sendChat(text, persona);
            setMessages((m) =>
                m.map((msg) =>
                    msg.id === streamId
                        ? {
                              id: `assistant-${Date.now()}`,
                              role: "assistant",
                              content: result?.reply || "Sin respuesta",
                              provider: result?.provider,
                          }
                        : msg,
                ),
            );
        } catch (e) {
            setMessages((m) =>
                m.map((msg) =>
                    msg.id === streamId
                        ? { id: `err-${Date.now()}`, role: "assistant", content: `Error: ${e}` }
                        : msg,
                ),
            );
        } finally {
            setLoading(false);
        }
    }, [input, loading, persona, provider]);

    return (
        <div className="flex flex-col h-full">
            {/* Header */}
            <div className="px-6 py-4 border-b border-white/5 flex items-center gap-3">
                <motion.div
                    animate={{ opacity: [0.6, 1, 0.6] }}
                    transition={{ repeat: Infinity, duration: 2 }}
                    className="w-2 h-2 rounded-full bg-aura-green"
                />
                <h1 className="text-lg font-semibold tracking-wide text-aura-cyan">AURA</h1>
                <span className="text-xs text-aura-muted">
                    {persona} · {provider}
                </span>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
                {messages.length === 0 && (
                    <div className="flex items-center justify-center h-full text-aura-muted text-sm">
                        Envía un mensaje para empezar a conversar con AURA...
                    </div>
                )}
                {messages.map((msg) => (
                    <MessageItem key={msg.id} msg={msg} />
                ))}
                <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-white/5 space-y-2">
                <div className="flex gap-2">
                    <input
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && send()}
                        placeholder="Escribe un mensaje a AURA..."
                        disabled={loading}
                        className="flex-1 bg-aura-panel border border-white/10 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-aura-cyan/50 disabled:opacity-40"
                    />
                    <button
                        onClick={send}
                        disabled={loading || !input.trim()}
                        className="px-5 py-2.5 bg-aura-cyan/20 border border-aura-cyan/40 text-aura-cyan rounded-xl text-sm hover:bg-aura-cyan/30 transition disabled:opacity-40"
                    >
                        {loading ? "..." : "Enviar"}
                    </button>
                </div>
            </div>
        </div>
    );
}
