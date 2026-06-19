"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiPost, apiGet, apiStream } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { CompletenessScore } from "@/components/CompletenessScore";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface StartResult {
  session_id: string;
  status: "created" | "resumed";
  messages: Array<{ role: "user" | "assistant"; content: string }>;
}

interface SessionStatus {
  id: string;
  status: string;
  message_count: number;
  gaps_total: number;
  gaps_resolved: number;
  profile_complete: boolean;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  hidden?: boolean;
}

const STATIC_WELCOME: ChatMessage = {
  role: "assistant",
  content:
    "Hej! Jeg er klar til at hjælpe dig med at bygge din komplette karriereprofil.\n\nJeg vil stille dig en række spørgsmål for at afdække dine erfaringer, præstationer og kompetencer i dybden.\n\nLad os begynde — fortæl mig om din nuværende eller seneste stilling: hvad var din titel, og hvad var din primære rolle?",
};

export default function InterviewPage() {
  const router = useRouter();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionStatus, setSessionStatus] = useState<SessionStatus | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scoreRefresh, setScoreRefresh] = useState(0);
  const [coldStartWait, setColdStartWait] = useState(false);
  const [interviewComplete, setInterviewComplete] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    initSession();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function initSession() {
    setLoading(true);
    setError(null);

    const coldTimer = setTimeout(() => setColdStartWait(true), 5000);

    try {
      const result = await apiPost<StartResult>("/discovery/start", {});
      setSessionId(result.session_id);

      if (result.status === "resumed" && result.messages.length > 0) {
        // Filter hidden messages (welcome trigger) from display
        const visible = result.messages
          .filter((m) => !(m.role === "user" && m.content.startsWith("Start interviewet")))
          .map((m) => ({ role: m.role, content: m.content }));
        setMessages(visible.length > 0 ? visible : [STATIC_WELCOME]);
      } else if (result.status === "resumed") {
        try {
          const hist = await apiGet<{ messages: Array<{ role: "user" | "assistant"; content: string }> }>(
            `/discovery/${result.session_id}/messages`
          );
          const visible = (hist.messages || []).filter(
            (m) => !(m.role === "user" && m.content.startsWith("Start interviewet"))
          );
          setMessages(visible.length > 0 ? visible : [STATIC_WELCOME]);
        } catch {
          setMessages([STATIC_WELCOME]);
        }
      } else {
        setMessages([STATIC_WELCOME]);
      }

      loadStatus(result.session_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kunne ikke starte interview.");
      setMessages([STATIC_WELCOME]);
    } finally {
      clearTimeout(coldTimer);
      setColdStartWait(false);
      setLoading(false);
    }
  }

  async function loadStatus(sid: string) {
    try {
      const status = await apiGet<SessionStatus>(`/discovery/${sid}`);
      setSessionStatus(status);
      if (status.profile_complete) {
        setInterviewComplete(true);
      }
    } catch {
      // Status er non-critical
    }
  }

  const sendMessage = useCallback(async () => {
    if (!input.trim() || sending) return;
    if (!sessionId) {
      setError("Session ikke klar — prøv at genindlæse siden.");
      return;
    }

    const userMsg = input.trim();
    setInput("");
    setSending(true);
    setError(null);

    setMessages((prev) => [
      ...prev,
      { role: "user", content: userMsg },
      { role: "assistant", content: "", streaming: true },
    ]);

    try {
      await apiStream(
        `/discovery/${sessionId}/message`,
        { message: userMsg },
        (chunk) => {
          setMessages((prev) =>
            prev.map((m, i) =>
              i === prev.length - 1 ? { ...m, content: m.content + chunk } : m
            )
          );
        },
        (payload) => {
          // Rens sentinel fra display og stop streaming-indikator
          setMessages((prev) =>
            prev.map((m, i) => {
              if (i !== prev.length - 1) return m;
              return {
                ...m,
                streaming: false,
                content: m.content.replace("[INTERVIEW_COMPLETE]", "").trim(),
              };
            })
          );
          if (payload?.interview_complete) {
            setInterviewComplete(true);
          }
          setScoreRefresh((n) => n + 1);
          loadStatus(sessionId);
        },
        (errMsg) => {
          setError(errMsg || "AI svarede ikke — prøv igen.");
          setMessages((prev) => prev.slice(0, -1));
        }
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Svar mislykkedes.");
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setSending(false);
      textareaRef.current?.focus();
    }
  }, [input, sessionId, sending]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  const gapsProgress =
    sessionStatus && sessionStatus.gaps_total > 0
      ? Math.round((sessionStatus.gaps_resolved / sessionStatus.gaps_total) * 100)
      : null;

  return (
    <div className="flex h-full gap-6">
      {/* Chat area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900">AI-Interview</h1>
            <p className="text-sm text-slate-500">
              Fortæl om dine erfaringer — AI&apos;en udfylder din profil
            </p>
          </div>
          {gapsProgress !== null && (
            <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2">
              <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-blue-500 transition-all"
                  style={{ width: `${gapsProgress}%` }}
                />
              </div>
              <span className="text-xs text-slate-500">
                {sessionStatus?.gaps_resolved}/{sessionStatus?.gaps_total} gaps dækket
              </span>
            </div>
          )}
        </div>

        {loading ? (
          <div className="flex flex-1 items-center justify-center">
            <div className="text-center">
              <svg
                className="mx-auto mb-3 h-8 w-8 animate-spin text-blue-600"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              <p className="text-sm text-slate-500">Forbereder interview…</p>
              {coldStartWait && (
                <p className="mt-2 text-xs text-slate-400">
                  Backend starter op — dette kan tage 30-60 sek.
                </p>
              )}
            </div>
          </div>
        ) : (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto rounded-xl border border-slate-200 bg-white">
              <div className="space-y-0 divide-y divide-slate-50 p-2">
                {messages.length === 0 && (
                  <div className="flex h-32 items-center justify-center">
                    <p className="text-sm text-slate-400">Starter interview…</p>
                  </div>
                )}

                {messages.map((msg, i) => (
                  <div
                    key={i}
                    className={cn(
                      "flex gap-3 p-4",
                      msg.role === "user" ? "flex-row-reverse" : "flex-row"
                    )}
                  >
                    <div
                      className={cn(
                        "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                        msg.role === "assistant"
                          ? "bg-blue-600 text-white"
                          : "bg-slate-200 text-slate-600"
                      )}
                    >
                      {msg.role === "assistant" ? "AI" : "Dig"}
                    </div>

                    <div
                      className={cn(
                        "max-w-[85%] rounded-2xl px-4 py-3 text-sm",
                        msg.role === "user"
                          ? "rounded-tr-sm bg-blue-600 text-white"
                          : "rounded-tl-sm bg-slate-50 text-slate-800"
                      )}
                    >
                      <p className="whitespace-pre-wrap leading-relaxed">
                        {msg.content}
                      </p>
                      {msg.streaming && msg.content.length === 0 && (
                        <span className="flex gap-1 pt-1">
                          {[0, 150, 300].map((delay) => (
                            <span
                              key={delay}
                              className="h-2 w-2 animate-bounce rounded-full bg-slate-400"
                              style={{ animationDelay: `${delay}ms` }}
                            />
                          ))}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={bottomRef} />
              </div>
            </div>

            {error && (
              <div className="mt-2 flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-3 py-2">
                <p className="text-xs text-red-700">{error}</p>
                <div className="flex gap-3">
                  {!sessionId && (
                    <button
                      className="text-xs font-medium text-blue-600 underline"
                      onClick={initSession}
                    >
                      Prøv igen
                    </button>
                  )}
                  <button
                    className="text-xs text-red-500 underline"
                    onClick={() => setError(null)}
                  >
                    Luk
                  </button>
                </div>
              </div>
            )}

            {/* Interview complete CTA */}
            {interviewComplete ? (
              <div className="mt-3 rounded-xl border border-green-200 bg-green-50 p-4">
                <p className="mb-3 text-sm font-semibold text-green-800">
                  Interview afsluttet — din profil er opdateret!
                </p>
                <p className="mb-4 text-xs text-green-700">
                  Alle svar er gemt og din Career Memory er opdateret. Generer nu dit opdaterede Master CV.
                </p>
                <Button
                  onClick={() => router.push("/cv")}
                  className="w-full bg-green-600 hover:bg-green-700"
                >
                  Generer Master CV
                </Button>
              </div>
            ) : (
              /* Input */
              <div className="mt-3 flex gap-2">
                <Textarea
                  ref={textareaRef}
                  rows={3}
                  placeholder="Skriv dit svar… (Enter sender, Shift+Enter = ny linje)"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={sending}
                  className="flex-1"
                />
                <Button
                  onClick={sendMessage}
                  disabled={!input.trim() || sending}
                  className="self-end px-5"
                >
                  {sending ? "…" : "Send"}
                </Button>
              </div>
            )}

            {!interviewComplete && (
              <p className="mt-1.5 text-center text-xs text-slate-400">
                Dine svar gemmes og bruges til at opdatere din profil automatisk
              </p>
            )}
          </>
        )}
      </div>

      {/* Score sidebar */}
      <aside className="w-64 shrink-0">
        <div className="sticky top-0 space-y-4">
          <div className="rounded-xl border border-slate-200 bg-slate-900 p-4">
            <h2 className="mb-4 text-sm font-semibold text-slate-200">
              Profil fuldstændighed
            </h2>
            <CompletenessScore refreshKey={scoreRefresh} />
          </div>

          {sessionStatus && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h3 className="mb-3 text-xs font-semibold text-slate-700">Session</h3>
              <div className="space-y-2 text-xs text-slate-500">
                <div className="flex justify-between">
                  <span>Beskeder</span>
                  <span className="font-medium text-slate-700">
                    {sessionStatus.message_count}
                  </span>
                </div>
                {sessionStatus.gaps_total > 0 && (
                  <div className="flex justify-between">
                    <span>Gaps dækket</span>
                    <span className="font-medium text-slate-700">
                      {sessionStatus.gaps_resolved}/{sessionStatus.gaps_total}
                    </span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span>Status</span>
                  <Badge variant={sessionStatus.profile_complete ? "success" : "info"}>
                    {sessionStatus.profile_complete ? "Komplet" : "Aktiv"}
                  </Badge>
                </div>
              </div>
            </div>
          )}

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-2 text-xs font-semibold text-slate-700">Tips</h3>
            <ul className="space-y-1.5 text-xs text-slate-500">
              <li>· Vær specifik med tal og procenter</li>
              <li>· Nævn teamstørrelse og budget</li>
              <li>· Beskriv din personlige rolle</li>
              <li>· Del hvad der gik godt OG hvad du lærte</li>
            </ul>
          </div>
        </div>
      </aside>
    </div>
  );
}
