"use client";

import { useState, FormEvent, useEffect, useRef } from 'react';

interface ChatHistoryEntry {
  user: string;
  bot: string;
}

interface ChatHistoryEntry {
  user: string;
  bot: string;
}

export default function HfChatPage() {
  const [message, setMessage] = useState<string>('');
  const [history, setHistory] = useState<ChatHistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isWarmingUp, setIsWarmingUp] = useState<boolean>(false); // New state for warming up message
  const [error, setError] = useState<string | null>(null);
  const chatWindowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [history]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!message.trim() || isLoading) return;

    const currentMessage = message; // Capture message before clearing input
    const newHistory: ChatHistoryEntry[] = [...history, { user: currentMessage, bot: '' }];
    setHistory(newHistory);
    setMessage('');
    setIsLoading(true);
    setError(null);

    const warmupTimeout = setTimeout(() => {
        setIsWarmingUp(true);
    }, 10000); // Show warming up message after 10 seconds

    try {
      const response = await fetch('/api/hf-chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: currentMessage,
          history: history.map(entry => [entry.user, entry.bot]), // Format for Gradio ChatInterface backend
          systemPrompt: "Eres AURA, un asistente de IA avanzado.", // Default system prompt
          temperature: 0.7,
          maxTokens: 512,
        }),
      });

      clearTimeout(warmupTimeout);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.details || errorData.error || 'Error desconocido del servidor');
      }

      const data = await response.json();
      setHistory(prevHistory => {
        const updatedHistory = [...prevHistory];
        updatedHistory[updatedHistory.length - 1].bot = data.message; // Update the last bot message
        return updatedHistory;
      });
    } catch (err: unknown) {
      clearTimeout(warmupTimeout);
      console.error('Error enviando mensaje:', err);
      setError(
        err instanceof Error
          ? err.message
          : 'Error al conectar con el asistente. Intenta de nuevo más tarde.',
      );
      setHistory(prevHistory => {
        const updatedHistory = [...prevHistory];
        // Append an error message from the bot if the last entry is still empty
        if (updatedHistory[updatedHistory.length - 1].bot === '') {
            updatedHistory[updatedHistory.length - 1].bot = `Error: ${
              err instanceof Error ? err.message : 'Error desconocido'
            }`;
        }
        return updatedHistory;
      });
    } finally {
      setIsLoading(false);
      setIsWarmingUp(false); // Reset warming up state
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-gray-100 p-4">
      <h1 className="text-3xl font-bold mb-6 text-center text-blue-400">AURA Chat (Hugging Face)</h1>

      <div ref={chatWindowRef} className="flex-1 overflow-y-auto p-4 rounded-lg bg-gray-800 mb-4 shadow-inner">
        {history.length === 0 && !isWarmingUp && (
          <p className="text-gray-400 text-center">Inicia una conversación con AURA...</p>
        )}
        {history.map((entry, index) => (
          <div key={index} className="mb-4">
            <div className="flex justify-end mb-1">
              <span className="bg-blue-600 text-white rounded-lg px-4 py-2 max-w-lg shadow-md">
                {entry.user}
              </span>
            </div>
            {entry.bot && (
              <div className="flex justify-start">
                <span className="bg-gray-700 text-gray-100 rounded-lg px-4 py-2 max-w-lg shadow-md">
                  {entry.bot}
                </span>
              </div>
            )}
          </div>
        ))}
        {isLoading && !isWarmingUp && (
          <div className="flex justify-start">
            <span className="bg-gray-700 text-gray-100 rounded-lg px-4 py-2 max-w-lg shadow-md animate-pulse">
              Escribiendo...
            </span>
          </div>
        )}
        {isWarmingUp && (
          <div className="flex justify-start">
            <span className="bg-yellow-600 text-white rounded-lg px-4 py-2 max-w-lg shadow-md animate-pulse">
              Despertando el Space de AURA... Esto puede tardar unos segundos.
            </span>
          </div>
        )}
      </div>

      {error && (
        <div className="bg-red-800 text-white p-3 rounded-lg mb-4 text-center shadow-md">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex space-x-2">
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Escribe tu mensaje..."
          className="flex-1 p-3 rounded-lg bg-gray-700 text-gray-100 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
          disabled={isLoading}
        />
        <button
          type="submit"
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-lg shadow-md transition duration-200 ease-in-out disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={isLoading}
        >
          {isLoading ? 'Enviando...' : 'Enviar'}
        </button>
      </form>
    </div>
  );
}
