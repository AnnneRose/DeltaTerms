import { useState, useRef, useEffect } from "react";
import { useParams, useNavigate } from "react-router";
import { Send, ArrowLeft, AlertTriangle } from "lucide-react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

type ServiceData = {
  name: string;
  delta: string | null;
};

export function Chat() {
  const { serviceId } = useParams<{ serviceId: string }>();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [serviceData, setServiceData] = useState<ServiceData | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const conversationIdRef = useRef<string>(
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID().slice(0, 8)
      : Math.random().toString(36).slice(2, 10)
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadService() {
      try {
        const response = await fetch("/api/tos-history", { credentials: "include" });
        if (!response.ok) throw new Error(`Request failed (${response.status})`);
        const items: { id: number; chatbot_name: string; delta: string | null }[] =
          await response.json();
        const match = items.find((item) => String(item.id) === serviceId);
        if (cancelled || !match) return;

        const service: ServiceData = {
          name: match.chatbot_name,
          delta: match.delta,
        };
        setServiceData(service);

        const body = service.delta
          ? `Here's a summary of changes detected in the latest Terms of Service:\n\n**⚠️ Key Changes:**\n${service.delta}`
          : "This is the first version uploaded for this service — no previous terms to compare against yet.";

        setMessages([
          {
            id: "init",
            role: "assistant",
            content: `📋 **${service.name}**\n\n${body}\n\nFeel free to ask me any questions about these terms!`,
            timestamp: new Date(),
          },
        ]);
      } catch (err) {
        console.error("Failed to load service:", err);
      }
    }
    void loadService();
    return () => {
      cancelled = true;
    };
  }, [serviceId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = inputValue.trim();
    if (!trimmed || isSending || !serviceId) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    };

    const historyForRequest = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");
    setIsSending(true);
    setSendError(null);

    try {
      const response = await fetch(`/api/chat/${serviceId}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          history: historyForRequest,
          conversation_id: conversationIdRef.current,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.error || `Request failed (${response.status})`);
      }

      const aiResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.reply ?? "",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiResponse]);
    } catch (err) {
      setSendError(err instanceof Error ? err.message : "Failed to get a reply");
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto h-[calc(100vh-8rem)]">
      <div className="mb-4">
        <button
          onClick={() => navigate("/dashboard")}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors"
        >
          <ArrowLeft size={20} />
          <span>Back to Dashboard</span>
        </button>
      </div>

      <div className="bg-white rounded-lg shadow-md h-full flex flex-col">
        <div className="border-b border-gray-200 p-4">
          <h2 className="text-xl font-semibold text-gray-900">{serviceData?.name ?? "Loading…"}</h2>
          <p className="text-sm text-gray-500">AI-powered ToS Analysis & Q&A</p>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-lg p-4 ${
                  message.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-900"
                }`}
              >
                {message.role === "assistant" && message.content.includes("⚠️") ? (
                  <div className="space-y-2">
                    {message.content.split("\n").map((line, idx) => {
                      if (line.includes("⚠️") || line.includes("📋")) {
                        return (
                          <div key={idx} className="font-semibold">
                            {line}
                          </div>
                        );
                      }
                      if (line.startsWith("•")) {
                        return (
                          <div key={idx} className="flex items-start gap-2 text-sm">
                            <AlertTriangle size={16} className="text-orange-600 mt-0.5 flex-shrink-0" />
                            <span>{line.substring(1).trim()}</span>
                          </div>
                        );
                      }
                      return line ? <div key={idx}>{line}</div> : null;
                    })}
                  </div>
                ) : (
                  <div className="whitespace-pre-wrap">{message.content}</div>
                )}
                <div
                  className={`text-xs mt-2 ${
                    message.role === "user" ? "text-blue-100" : "text-gray-500"
                  }`}
                >
                  {message.timestamp.toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))}
          {isSending && (
            <div className="flex justify-start" aria-live="polite">
              <div className="max-w-[80%] rounded-lg p-4 bg-gray-100 text-gray-600 italic">
                Thinking…
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="border-t border-gray-200 p-4">
          {sendError && (
            <div className="mb-2 p-2 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm" role="alert">
              {sendError}
            </div>
          )}
          <form onSubmit={handleSend} className="flex gap-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask about specific terms, changes, or implications..."
              className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              className="bg-blue-600 text-white p-2 rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
              disabled={!inputValue.trim() || isSending}
            >
              <Send size={20} />
            </button>
          </form>
          <p className="text-xs text-gray-500 mt-2">
            Example questions: "What data do they collect?", "Can I opt out of arbitration?", "What changed from the last version?"
          </p>
        </div>
      </div>
    </div>
  );
}
