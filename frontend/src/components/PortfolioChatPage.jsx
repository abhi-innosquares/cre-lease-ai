import { useEffect, useRef, useState } from "react";
import { askPortfolioQuestion, getGreeting } from "../api";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Send, Trash2 } from "lucide-react";

const PORTFOLIO_CHAT_STORAGE_KEY = "portfolio_chat_history_v1";

function loadPortfolioHistory() {
  try {
    const raw = localStorage.getItem(PORTFOLIO_CHAT_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

const EXAMPLE_PROMPTS = [
  "Which leases end in January 2025?",
  "Show high-risk leases with renewal risk score above 0.5",
  "Which leases have termination options?",
];

function extractLastReferencedLeaseId(history) {
  if (!Array.isArray(history)) return null;
  const leasePattern = /\blease\s+(\d+)\b/i;
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const message = history[i]?.content || "";
    const match = leasePattern.exec(message);
    if (match) {
      return Number(match[1]);
    }
  }
  return null;
}

function PortfolioChatPage() {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState(() => loadPortfolioHistory());
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const currentLeaseContext = extractLastReferencedLeaseId(history);

  // Fetch and add greeting message on first load
  useEffect(() => {
    if (history.length !== 0) {
      return;
    }

    getGreeting()
      .then((res) => {
        const greetingMsg = { role: "assistant", content: res.data.greeting };
        setHistory((existingHistory) => (existingHistory.length === 0 ? [greetingMsg] : existingHistory));
      })
      .catch((err) => {
        console.error("Failed to fetch greeting:", err);
      });
  }, [history.length]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history]);

  useEffect(() => {
    try {
      localStorage.setItem(PORTFOLIO_CHAT_STORAGE_KEY, JSON.stringify(history));
    } catch {
      // Ignore storage failures and keep chat functional in-memory.
    }
  }, [history]);

  const sendQuestion = async (rawQuestion) => {
    const trimmed = (rawQuestion || "").trim();
    if (!trimmed) return;

    const userMsg = { role: "user", content: trimmed };
    setHistory((h) => [...h, userMsg]);
    setQuestion("");

    try {
      setLoading(true);
      const res = await askPortfolioQuestion({ user_query: trimmed, chat_history: history });
      setHistory((h) => [...h, { role: "assistant", content: res.data.answer || "No answer returned." }]);
    } catch (err) {
      console.error(err);
      toast.error("Portfolio chat failed", { description: "Could not reach backend chat service." });
      setHistory((h) => [...h, { role: "assistant", content: "Error fetching answer." }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendQuestion(question);
    }
  };

  const clearChat = () => {
    // Refetch greeting and reset
    getGreeting()
      .then((res) => {
        const greetingMsg = { role: "assistant", content: res.data.greeting };
        setHistory([greetingMsg]);
      })
      .catch(() => {
        setHistory([]);
      });
    setQuestion("");
    try {
      localStorage.removeItem(PORTFOLIO_CHAT_STORAGE_KEY);
    } catch {
      // Ignore storage failures and keep chat functional.
    }
  };

  return (
    <Card className="enterprise-card">
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <CardTitle>Portfolio Chat Assistant</CardTitle>
          <Button type="button" variant="outline" size="sm" onClick={clearChat} disabled={!history.length || loading}>
            <Trash2 className="h-4 w-4" />
            Clear Chat
          </Button>
        </div>
        <CardDescription>
          Ask questions across all uploaded leases. The assistant searches portfolio-wide data, not a single file.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="rounded-lg border bg-white/50 p-3">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">Try asking</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {EXAMPLE_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                className="rounded-full border bg-white px-3 py-1 text-xs text-slate-700 transition hover:bg-slate-50"
                onClick={() => sendQuestion(prompt)}
                disabled={loading}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2 rounded-lg border bg-white/50 px-3 py-2">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">Current Lease Context</p>
          <span className="inline-flex rounded-full border bg-cyan-50 px-2.5 py-1 text-xs font-semibold text-cyan-700">
            {currentLeaseContext ? `Lease ${currentLeaseContext}` : "None"}
          </span>
        </div>

        <div className="flex max-h-[420px] min-h-[220px] flex-col gap-3 overflow-y-auto rounded-lg border bg-white/50 p-3">
          {history.length === 0 && (
            <p className="m-auto text-sm text-muted-foreground">No messages yet. Ask a portfolio-level question.</p>
          )}
          {history.map((msg, i) => (
            <div
              key={i}
              className={`rounded-lg px-3 py-2 text-sm leading-6 whitespace-pre-wrap ${
                msg.role === "user"
                  ? "self-end bg-cyan-600 text-white"
                  : "self-start bg-slate-100 text-slate-800"
              }`}
            >
              {msg.role === "assistant" ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                    ul: ({ children }) => <ul className="mb-2 list-disc pl-5 last:mb-0">{children}</ul>,
                    ol: ({ children }) => <ol className="mb-2 list-decimal pl-5 last:mb-0">{children}</ol>,
                    li: ({ children }) => <li className="mb-1 last:mb-0">{children}</li>,
                    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                  }}
                >
                  {String(msg.content || "")}
                </ReactMarkdown>
              ) : (
                msg.content
              )}
            </div>
          ))}
          {loading && (
            <div className="self-start rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-500 animate-pulse">
              Thinking...
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="flex gap-2">
          <Input
            type="text"
            placeholder="Example: Which leases expire in Q1 2025?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <Button size="sm" onClick={() => sendQuestion(question)} disabled={loading || !question.trim()}>
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default PortfolioChatPage;
