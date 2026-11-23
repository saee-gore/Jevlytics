"use client";

import { useMutation } from "@tanstack/react-query";
import { MessageSquare, Send, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ResultView } from "@/components/analytics/result-view";
import { LoadingState, ErrorState } from "@/components/states/states";
import { Button, Input } from "@/components/ui/primitives";
import { recordActivity } from "@/lib/activity";
import { clarifyOptions } from "@/lib/clarify";
import { ask } from "@/lib/data";
import type { ChatResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

const STARTERS = [
  "How many transactions did we process last month?",
  "What was our transaction volume this quarter?",
  "Compare credit and debit card performance.",
  "What are our most common decline reasons?",
  "What is our decline rate by card network?",
  "How much transaction volume was settled last month?",
  "Did our chargeback rate increase this quarter?",
  "Show transaction volume by region.",
];

type Turn =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "assistant"; response: ChatResponse; question: string }
  | { id: string; role: "error"; text: string };

interface ChatWidgetProps {
  /** When set, questions cannot be sent and this text explains why (for example, no token yet). */
  blockedReason?: string | null;
}

/**
 * Floating assistant at the bottom-left of the page. A launcher button opens the chat panel.
 * The panel stays mounted when closed, so the conversation is kept while the user navigates within the page.
 */
export function ChatWidget({ blockedReason = null }: ChatWidgetProps) {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const counter = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const send = useMutation({
    mutationFn: async (question: string) => ask(question),
    onMutate: (question) => {
      counter.current += 1;
      setTurns((t) => [...t, { id: `u${counter.current}`, role: "user", text: question }]);
    },
    onSuccess: (response, question) => {
      counter.current += 1;
      setTurns((t) => [...t, { id: `a${counter.current}`, role: "assistant", response, question }]);
      recordActivity({ question, status: response.status, tool: response.tool_used, requestId: response.request_id });
    },
    onError: (error, question) => {
      counter.current += 1;
      setTurns((t) => [...t, { id: `e${counter.current}`, role: "error", text: (error as Error).message }]);
      recordActivity({ question, status: "error", tool: null, requestId: null });
    },
  });

  // Keep the newest message in view. Scrolls the message list only, not the page.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [turns.length, send.isPending, open]);

  // Focus the input when the panel opens, and close on Escape.
  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const blocked = Boolean(blockedReason);

  function submit(text: string) {
    const question = text.trim();
    if (!question || send.isPending || blocked) return;
    setDraft("");
    send.mutate(question);
  }

  return (
    <>
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-expanded={false}
          aria-controls="assistant-panel"
          className="fixed bottom-6 right-6 z-40 flex items-center gap-2.5 rounded-full bg-brand py-3 pl-3.5 pr-5 text-sm font-semibold text-white shadow-glow transition hover:-translate-y-0.5 hover:shadow-panel"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/20">
            <MessageSquare className="h-4 w-4" aria-hidden />
          </span>
          AI Assistant
          {turns.length > 0 ? (
            <span className="rounded-full bg-white/25 px-2 py-0.5 text-[11px]">{turns.length}</span>
          ) : null}
        </button>
      ) : null}

      <section
        id="assistant-panel"
        aria-label="AI Assistant"
        className={cn(
          "fixed bottom-6 right-6 z-50 h-[min(58rem,calc(100vh-3rem))] w-[min(34rem,calc(100vw-3rem))] flex-col overflow-hidden rounded-3xl bg-surface shadow-panel ring-1 ring-line",
          open ? "flex" : "hidden",
        )}
      >
        <header className="relative overflow-hidden bg-brand px-5 py-4 text-white">
          <div className="pointer-events-none absolute -right-8 -top-10 h-32 w-32 rounded-full bg-white/10" aria-hidden />
          <div className="relative flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white/20 ring-1 ring-white/30">
              <Sparkles className="h-5 w-5" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <h2 className="text-base font-semibold tracking-tight">Payments assistant</h2>
              <p className="flex items-center gap-1.5 text-xs text-white/80">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" aria-hidden />
                Figures come only from analytics
              </p>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close assistant"
              className="rounded-full p-1.5 text-white/90 transition hover:bg-white/15 hover:text-white"
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </header>

        <div
          ref={scrollRef}
          aria-live="polite"
          className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto bg-gradient-to-b from-canvas to-surface px-4 py-4"
        >
          {turns.length === 0 ? (
            <div className="space-y-4">
              <div className="flex gap-2.5">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand text-white">
                  <Sparkles className="h-3.5 w-3.5" aria-hidden />
                </span>
                <div className="rounded-2xl rounded-tl-sm bg-surface px-4 py-3 text-sm text-ink shadow-card ring-1 ring-line">
                  Hi! Ask me about volume, declines, settlements or chargebacks. Pick a suggestion or type your own.
                </div>
              </div>
              <div className="grid gap-2">
                {STARTERS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => submit(q)}
                    disabled={send.isPending || blocked}
                    className="rounded-xl bg-surface px-3.5 py-2.5 text-left text-xs font-medium text-ink ring-1 ring-line transition hover:-translate-y-0.5 hover:text-violet hover:shadow-lift disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {turns.map((turn) => {
            if (turn.role === "user") {
              return (
                <div key={turn.id} className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-brand px-4 py-2.5 text-sm text-white shadow-glow">
                    {turn.text}
                  </div>
                </div>
              );
            }
            if (turn.role === "error") {
              return <ErrorState key={turn.id} message={turn.text} />;
            }
            return (
              <div key={turn.id} className="flex max-w-[95%] gap-2.5">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand text-white">
                  <Sparkles className="h-3.5 w-3.5" aria-hidden />
                </span>
                <div className="min-w-0 flex-1 space-y-3">
                  <ResultView response={turn.response} />
                  {turn.response.status === "clarification_required" ? (
                    <div className="space-y-2 rounded-2xl bg-surface p-3 shadow-card ring-1 ring-line">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-violet">Did you mean one of these?</p>
                      <div className="grid gap-2">
                        {clarifyOptions(turn.question).map((o) => (
                          <button
                            key={o.label}
                            type="button"
                            onClick={() => submit(o.question)}
                            disabled={send.isPending || blocked}
                            className="rounded-xl bg-canvas px-3 py-2 text-left ring-1 ring-line transition hover:bg-violet-soft hover:ring-violet/40 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            <span className="block text-sm font-medium text-ink">{o.label}</span>
                            <span className="mt-0.5 block text-xs text-muted">{o.question}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
          {send.isPending ? <LoadingState label="Checking your question and retrieving figures…" /> : null}
        </div>

        <div className="space-y-3 border-t border-line bg-surface px-4 py-3">
          {blocked ? (
            <p className="rounded-xl bg-amber-soft px-3 py-2 text-xs font-medium text-warn ring-1 ring-amber/20">{blockedReason}</p>
          ) : null}
          {turns.length > 0 ? (
            <div className="flex max-h-40 flex-col gap-1.5 overflow-y-auto pr-1" aria-label="Suggested questions">
              {STARTERS.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => submit(q)}
                  disabled={send.isPending || blocked}
                  className="w-full rounded-xl bg-canvas px-3 py-2 text-left text-xs font-medium text-ink ring-1 ring-line transition hover:bg-violet-soft hover:text-violet disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {q}
                </button>
              ))}
            </div>
          ) : null}
          <form
            className={cn(
              "flex items-center gap-2 rounded-2xl bg-canvas p-1.5 ring-1 ring-line transition focus-within:bg-surface focus-within:ring-2 focus-within:ring-violet/50",
              blocked && "opacity-60",
            )}
            onSubmit={(e) => {
              e.preventDefault();
              submit(draft);
            }}
          >
            <label className="sr-only" htmlFor="question">Ask a question</label>
            <Input
              id="question"
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={blocked ? "Sign in to ask questions" : "Ask about volume, declines…"}
              maxLength={4000}
              disabled={blocked}
              className="h-10 border-0 bg-transparent shadow-none focus-visible:ring-0"
            />
            <Button
              type="submit"
              className="h-10 rounded-xl bg-brand px-4 text-white shadow-glow hover:opacity-95 disabled:opacity-40"
              disabled={!draft.trim() || send.isPending || blocked}
            >
              <Send className="h-4 w-4" aria-hidden /> Send
            </Button>
          </form>
        </div>
      </section>
    </>
  );
}
