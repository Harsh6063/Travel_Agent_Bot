"use client";

import { useState } from "react";
import axios from "axios";

export default function Chat() {
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const [budget, setBudget] = useState("medium");
  const [sessionId, setSessionId] = useState("");
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMsg = { role: "user", text: input };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await axios.post("http://localhost:8000/chat", {
        query: input,
        budget,
        session_id: sessionId,
      });

      setSessionId(res.data.session_id);

      const botMsg = {
        role: "bot",
        text: res.data.response,
        results: res.data.results,
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      console.error(err);
    }

    setInput("");
    setLoading(false);
  };

  return (
    <div className="h-screen bg-[#0b1120] text-white flex flex-col items-center">
      {/* HEADER */}
      <div className="w-full max-w-3xl p-4 text-center text-xl font-semibold border-b border-gray-800">
        🌍 Travel AI Assistant
      </div>

      {/* CHAT AREA */}
      <div className="flex-1 w-full max-w-3xl overflow-y-auto p-4 space-y-6">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${
              m.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`max-w-[75%] px-4 py-3 rounded-2xl ${
                m.role === "user"
                  ? "bg-blue-600"
                  : "bg-gray-800 border border-gray-700"
              }`}
            >
              <p className="text-sm leading-relaxed">{m.text}</p>

              {/* RESULTS */}
              {m.results && (
                <div className="mt-4 space-y-3">
                  {m.results.map((r: any, idx: number) => (
                    <div
                      key={idx}
                      className="bg-black/40 p-3 rounded-lg border border-gray-700"
                    >
                      <div className="flex justify-between items-center">
                        <span className="font-semibold text-white">
                          📍 {r.Destination}
                        </span>
                        <span className="text-xs bg-gray-700 px-2 py-1 rounded">
                          {r.Category}
                        </span>
                      </div>

                      {/* WEATHER */}
                      {r.Weather && r.Weather.temp !== "N/A" && (
                        <div className="mt-2 text-xs text-gray-300 flex gap-3 flex-wrap">
                          <span>🌡️ {r.Weather.temp}</span>
                          <span>☁️ {r.Weather.condition}</span>
                        </div>
                      )}

                      {/* STAYS */}
                      {Array.isArray(r.Stays) && r.Stays.length > 0 && (
                        <div className="mt-2 space-y-1">
                          {r.Stays.slice(0, 2).map((s: any, i: number) => (
                            <a
                              key={i}
                              href={s.link}
                              target="_blank"
                              className="block text-xs text-gray-300 hover:text-white"
                            >
                              💰 {s.price}
                            </a>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="text-gray-400 animate-pulse text-sm">
            🤖 Thinking...
          </div>
        )}
      </div>

      {/* INPUT BOX */}
      <div className="w-full max-w-3xl p-4 border-t border-gray-800">
        <div className="flex items-center gap-2 bg-gray-900 rounded-xl px-3 py-2">
          

          <input
            className="flex-1 bg-transparent outline-none text-sm"
            placeholder="Ask your travel plan..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          />

          {/* SEND BUTTON */}
          <button
            onClick={sendMessage}
            className="bg-blue-600 hover:bg-blue-500 p-2 rounded-full transition"
          >
            ➤
          </button>
        </div>
      </div>
    </div>
  );
}