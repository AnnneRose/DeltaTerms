import { useState, useRef, useEffect } from "react";
import { useParams, useNavigate } from "react-router";
import { Send, ArrowLeft, AlertTriangle } from "lucide-react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

// Mock data for the service
const mockServiceData: Record<string, { name: string; summary: string; flags: string[] }> = {
  "1": {
    name: "Google",
    summary: "Recent changes detected in Google's Terms of Service (Updated March 15, 2026)",
    flags: [
      "Data retention period extended from 18 to 24 months",
      "New clause allowing data sharing with third-party AI training partners",
      "Updated dispute resolution requiring binding arbitration",
    ],
  },
};

export function Chat() {
  const { serviceId } = useParams<{ serviceId: string }>();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const serviceData = mockServiceData[serviceId || ""] || {
    name: "New Service",
    summary: "Terms of Service uploaded successfully. Ask me anything about the content!",
    flags: ["First-time analysis - no previous version to compare"],
  };

  useEffect(() => {
    // Initialize with AI summary
    const initialMessage: Message = {
      id: "init",
      role: "assistant",
      content: `📋 **${serviceData.name}**\n\n${serviceData.summary}\n\n**⚠️ Key Flags:**\n${serviceData.flags.map((flag) => `• ${flag}`).join("\n")}\n\nFeel free to ask me any questions about these terms!`,
      timestamp: new Date(),
    };
    setMessages([initialMessage]);
  }, [serviceId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: inputValue,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");

    // Mock AI response
    setTimeout(() => {
      const aiResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `Based on the Terms of Service, here's what I found regarding "${inputValue}":\n\nThis is a mock response. In the full version, the AI would analyze the actual ToS content and provide detailed answers about specific clauses, implications, and comparisons with previous versions.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiResponse]);
    }, 1000);
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
          <h2 className="text-xl font-semibold text-gray-900">{serviceData.name}</h2>
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
          <div ref={messagesEndRef} />
        </div>

        <div className="border-t border-gray-200 p-4">
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
              disabled={!inputValue.trim()}
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
