// ═══════════════════════════════════════════════════════════════
// AMEChat.tsx — Interfaz de chat con servidores Colab IA
// Muestra estado de servidores, badge del modelo, selector de modo
// ═══════════════════════════════════════════════════════════════

import React, { useCallback, useEffect, useRef, useState } from "react";
import { ServerStatus } from "../components/ServerStatus";
import { ameChatService, ChatMessage } from "../services/AMEChatService";
import { ServerMode } from "../services/ColabServerService";

const MODELS = [
    { id: "nvidia/nemotron-3-super-120b-a12b:free", name: "Nemotron 120B", uncensored: true },
    { id: "deepseek/deepseek-v3-0324:free", name: "DeepSeek V3", uncensored: true },
    { id: "nousresearch/hermes-3-llama-3.1-405b", name: "Hermes 3 405B", uncensored: true },
    { id: "qwen/qwen3.7-max", name: "Qwen 3.7 Max", uncensored: true },
    { id: "google/gemini-flash-1.5", name: "Gemini Flash", uncensored: false },
];

export const AMEChat: React.FC = () => {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState("");
    const [isTyping, setIsTyping] = useState(false);
    const [showModel, setShowModel] = useState(false);
    const [showSettings, setShowSettings] = useState(false);
    const [model, setModel] = useState(MODELS[0]);
    const [serverMode, setServerMode] = useState<ServerMode>("auto");
    const messagesEnd = useRef<HTMLDivElement>(null);

    useEffect(() => {
        setMessages(ameChatService.getMessages());
        ameChatService.onMessage((msg) => {
            setMessages((prev) => [...prev, msg]);
            setIsTyping(false);
            setTimeout(() => messagesEnd.current?.scrollIntoView({ behavior: "smooth" }), 100);
        });
    }, []);

    const send = useCallback(async () => {
        const text = input.trim();
        if (!text) return;
        setInput("");
        setIsTyping(true);
        await ameChatService.sendMessage(text);
    }, [input]);

    const scanQR = useCallback(async () => {
        const mod = await import("../services/QRScannerService").catch(() => null);
        if (mod) await mod.qrScannerService.scan();
        setMessages(ameChatService.getMessages());
    }, []);

    const handleKey = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
        }
    };

    /** Etiqueta amigable del servidor que respondió */
    const serverLabel = (st?: string): string => {
        if (st === "code") return "Modelo Código";
        if (st === "general") return "Modelo General";
        if (st === "openrouter") return "OpenRouter";
        return "";
    };

    const renderMessage = (msg: ChatMessage) => {
        const isCode = msg.type === "code" || msg.content.includes("```");
        const rs =
            msg.role === "user"
                ? {
                      alignSelf: "flex-end" as const,
                      bg: "rgba(72,255,206,0.08)",
                      brd: "rgba(72,255,206,0.2)",
                      rad: "16px 16px 4px 16px",
                  }
                : {
                      alignSelf: "flex-start" as const,
                      bg: "rgba(100,200,255,0.06)",
                      brd: "rgba(100,200,255,0.12)",
                      rad: "16px 16px 16px 4px",
                  };
        const bubble = {
            maxWidth: "88%",
            alignSelf: rs.alignSelf,
            background: rs.bg,
            border: `0.5px solid ${rs.brd}`,
            borderRadius: rs.rad,
            padding: "9px 13px",
            fontSize: "13px",
            lineHeight: 1.55,
        };

        if (isCode) {
            const parts = msg.content.split(/(```[\w]*\n[\s\S]*?```)/g);
            return (
                <div key={msg.id} style={{ ...bubble, maxWidth: "95%" }}>
                    {parts.map((part, i) => {
                        if (part.startsWith("```")) {
                            const code = part.replace(/```[\w]*\n?/, "").replace(/```$/, "");
                            return (
                                <pre
                                    key={i}
                                    style={{
                                        background: "#161b22",
                                        border: "0.5px solid rgba(100,200,255,0.15)",
                                        borderRadius: "8px",
                                        padding: "10px 12px",
                                        fontFamily: "monospace",
                                        fontSize: "11px",
                                        overflowX: "auto",
                                        color: "#79c0ff",
                                        margin: "4px 0",
                                    }}
                                >
                                    {code}
                                </pre>
                            );
                        }
                        return <span key={i}>{part}</span>;
                    })}
                    <div
                        style={{
                            fontSize: "9px",
                            padding: "1px 6px",
                            borderRadius: "4px",
                            background: "rgba(100,200,255,0.08)",
                            color: "rgba(150,210,255,0.5)",
                            marginTop: "3px",
                        }}
                    >
                        {msg.metadata?.model || ""}
                    </div>
                </div>
            );
        }

        return (
            <div key={msg.id} style={bubble as any}>
                {msg.content}
                {msg.metadata?.serverType && msg.role === "agent" && (
                    <div
                        style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                            fontSize: "9px",
                            padding: "2px 6px",
                            borderRadius: "4px",
                            background: "rgba(100,200,255,0.08)",
                            color: "rgba(150,210,255,0.5)",
                            marginTop: "3px",
                        }}
                    >
                        <span>{msg.metadata.model}</span>
                        <span style={{ opacity: 0.6 }}>·</span>
                        <span>{serverLabel(msg.metadata.serverType)}</span>
                    </div>
                )}
            </div>
        );
    };

    /** Texto del modo actual */
    const modeLabel: Record<ServerMode, string> = {
        auto: "Auto",
        forceCode: "Forzar Código",
        forceGeneral: "Forzar General",
    };

    /** Ciclar modo */
    const cycleMode = (): void => {
        const modes: ServerMode[] = ["auto", "forceCode", "forceGeneral"];
        const idx = modes.indexOf(serverMode);
        const next = modes[(idx + 1) % modes.length];
        setServerMode(next);
        ameChatService.setServerMode(next);
    };

    return (
        <div
            style={{
                display: "flex",
                flexDirection: "column",
                height: "100vh",
                background: "#0a0e1a",
                color: "rgba(200,240,255,0.95)",
                fontFamily: "inherit",
            }}
        >
            {/* Header con selector de modo y ServerStatus */}
            <div
                style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    padding: "10px 14px",
                    borderBottom: "0.5px solid rgba(100,200,255,0.1)",
                    background: "rgba(10,14,26,0.95)",
                }}
            >
                <div
                    style={{
                        width: "34px",
                        height: "34px",
                        borderRadius: "50%",
                        background: "linear-gradient(135deg,#0f3460,#1a6b8a)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "18px",
                        border: "1px solid rgba(100,200,255,0.25)",
                    }}
                >
                    ⚕
                </div>
                <div style={{ flex: 1 }}>
                    <div style={{ fontSize: "13px", fontWeight: 500 }}>AME Agent</div>
                    <div
                        style={{
                            fontSize: "10px",
                            color: "#48ffce",
                            display: "flex",
                            alignItems: "center",
                            gap: "4px",
                        }}
                    >
                        <span
                            style={{
                                width: "5px",
                                height: "5px",
                                borderRadius: "50%",
                                background: "#48ffce",
                            }}
                        />
                        {model.name}
                    </div>
                </div>
                {/* Modo de servidor (clickeable) */}
                <div
                    onClick={cycleMode}
                    style={{
                        fontSize: "10px",
                        padding: "4px 8px",
                        borderRadius: "6px",
                        border: "0.5px solid rgba(72,255,206,0.2)",
                        background: "rgba(72,255,206,0.06)",
                        color: "#48ffce",
                        cursor: "pointer",
                    }}
                >
                    {modeLabel[serverMode]}
                </div>
                <div
                    onClick={() => setShowModel(!showModel)}
                    style={{
                        width: "36px",
                        height: "36px",
                        borderRadius: "50%",
                        border: "0.5px solid rgba(100,200,255,0.4)",
                        background: "rgba(100,200,255,0.1)",
                        color: "rgba(100,200,255,0.7)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        cursor: "pointer",
                        fontSize: "18px",
                    }}
                >
                    🤖
                </div>
                <div
                    onClick={() => setShowSettings(!showSettings)}
                    style={{
                        width: "36px",
                        height: "36px",
                        borderRadius: "50%",
                        border: "0.5px solid rgba(100,200,255,0.4)",
                        background: "rgba(100,200,255,0.1)",
                        color: "rgba(100,200,255,0.7)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        cursor: "pointer",
                        fontSize: "18px",
                    }}
                >
                    📡
                </div>
            </div>

            {showModel && (
                <div
                    style={{
                        background: "rgba(10,14,26,0.98)",
                        border: "0.5px solid rgba(100,200,255,0.15)",
                        borderRadius: "12px",
                        margin: "8px 14px",
                        padding: "10px",
                    }}
                >
                    <div
                        style={{
                            fontSize: "10px",
                            color: "rgba(150,210,255,0.5)",
                            marginBottom: "8px",
                            textTransform: "uppercase" as const,
                        }}
                    >
                        Seleccionar modelo
                    </div>
                    {MODELS.map((m) => (
                        <div
                            key={m.id}
                            onClick={() => {
                                ameChatService.setModel(m.id);
                                setModel(m);
                                setShowModel(false);
                            }}
                            style={{
                                padding: "8px 10px",
                                borderRadius: "8px",
                                cursor: "pointer",
                                background:
                                    model.id === m.id ? "rgba(72,255,206,0.08)" : "transparent",
                                border: `0.5px solid ${model.id === m.id ? "rgba(72,255,206,0.2)" : "transparent"}`,
                                marginBottom: "4px",
                            }}
                        >
                            <div style={{ fontSize: "12px" }}>{m.name}</div>
                            <div
                                style={{
                                    fontSize: "9px",
                                    color: m.uncensored ? "#48ffce" : "rgba(150,210,255,0.4)",
                                }}
                            >
                                {m.uncensored ? "✓ Sin censura" : "Estándar"}
                            </div>
                        </div>
                    ))}
                    <div
                        style={{
                            marginTop: "8px",
                            borderTop: "0.5px solid rgba(100,200,255,0.08)",
                            paddingTop: "8px",
                        }}
                    >
                        <div
                            style={{
                                fontSize: "9px",
                                color: "rgba(150,210,255,0.4)",
                                marginBottom: "4px",
                            }}
                        >
                            OpenRouter API Key
                        </div>
                        <input
                            type="password"
                            placeholder="sk-or-..."
                            style={{
                                width: "100%",
                                background: "rgba(100,200,255,0.05)",
                                border: "0.5px solid rgba(100,200,255,0.12)",
                                borderRadius: "8px",
                                padding: "6px 10px",
                                fontSize: "11px",
                                color: "rgba(200,240,255,0.9)",
                                outline: "none",
                            }}
                            onChange={(e) => ameChatService.setApiKey(e.target.value)}
                        />
                    </div>
                </div>
            )}

            {/* Panel de servidores Colab */}
            {showSettings && (
                <div
                    style={{
                        background: "rgba(10,14,26,0.98)",
                        border: "0.5px solid rgba(100,200,255,0.15)",
                        borderRadius: "12px",
                        margin: "8px 14px",
                        padding: "0",
                    }}
                >
                    <ServerStatus />
                    <div
                        style={{
                            borderTop: "0.5px solid rgba(100,200,255,0.08)",
                            padding: "8px 14px",
                            fontSize: "9px",
                            color: "rgba(150,210,255,0.4)",
                        }}
                    >
                        Sin Termux. Servidores desde Colab / QR.
                    </div>
                </div>
            )}

            <div
                style={{
                    flex: 1,
                    overflowY: "auto",
                    padding: "12px 14px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "10px",
                }}
            >
                {messages.length === 0 && (
                    <div
                        style={{
                            textAlign: "center",
                            marginTop: "40px",
                            color: "rgba(150,210,255,0.3)",
                            fontSize: "13px",
                        }}
                    >
                        <div style={{ fontSize: "40px", marginBottom: "12px" }}>⚕</div>
                        <div>AME Agent listo</div>
                        <div style={{ fontSize: "11px", marginTop: "6px" }}>Escribe un mensaje</div>
                    </div>
                )}
                {messages.map(renderMessage)}
                {isTyping && (
                    <div
                        style={{
                            padding: "10px 14px",
                            color: "rgba(150,210,255,0.4)",
                            fontSize: "12px",
                        }}
                    >
                        Escribiendo...
                    </div>
                )}
                <div ref={messagesEnd} />
            </div>

            <div
                style={{
                    padding: "10px 14px",
                    borderTop: "0.5px solid rgba(100,200,255,0.08)",
                    display: "flex",
                    gap: "8px",
                    alignItems: "flex-end",
                    background: "rgba(10,14,26,0.95)",
                }}
            >
                <div
                    onClick={scanQR}
                    style={{
                        width: "36px",
                        height: "36px",
                        borderRadius: "50%",
                        border: "0.5px solid rgba(100,200,255,0.25)",
                        background: "rgba(100,200,255,0.05)",
                        color: "rgba(100,200,255,0.6)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        cursor: "pointer",
                        fontSize: "18px",
                    }}
                >
                    📷
                </div>
                <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKey}
                    placeholder="Escribe tu mensaje..."
                    rows={1}
                    style={{
                        flex: 1,
                        background: "rgba(100,200,255,0.05)",
                        border: "0.5px solid rgba(100,200,255,0.12)",
                        borderRadius: "20px",
                        padding: "8px 14px",
                        fontSize: "13px",
                        color: "rgba(200,240,255,0.9)",
                        resize: "none",
                        minHeight: "36px",
                        maxHeight: "80px",
                        outline: "none",
                        fontFamily: "inherit",
                    }}
                />
                <div
                    onClick={send}
                    style={{
                        width: "36px",
                        height: "36px",
                        borderRadius: "50%",
                        border: "0.5px solid #48ffce40",
                        background: "#48ffce10",
                        color: "#48ffce",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        cursor: "pointer",
                        fontSize: "18px",
                    }}
                >
                    ➤
                </div>
            </div>
        </div>
    );
};

export default AMEChat;
