"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Mic, SendHorizontal, Volume2, VolumeX } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { docentConfig, docentCopy, docentStarterQuestions } from "@/data/docent";
import type { DocentChatState } from "./useDocentChat";
import type { VoiceState } from "./useVoice";

type ChatPanelProps = DocentChatState & { voice: VoiceState };

export function ChatPanel({
  messages,
  isStreaming,
  mode,
  send,
  voice,
}: ChatPanelProps) {
  const reduceMotion = useReducedMotion();
  const [input, setInput] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const nearBottomRef = useRef(true);

  // 사용자가 위로 스크롤해 읽는 중이면 자동 스크롤하지 않는다.
  const handleScroll = () => {
    const el = listRef.current;
    if (!el) return;
    nearBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  const lastContent = messages[messages.length - 1]?.content;
  useEffect(() => {
    const el = listRef.current;
    if (el && nearBottomRef.current) el.scrollTop = el.scrollHeight;
  }, [messages.length, lastContent]);

  const submit = () => {
    if (isStreaming) return;
    const text = input.trim();
    if (!text) return;
    setInput("");
    send(text);
  };

  const handleMic = () => {
    if (voice.listening) {
      voice.stopListening();
      return;
    }
    voice.startListening((transcript) => {
      setInput("");
      send(transcript);
    });
  };

  return (
    <div className="flex h-[60vh] min-h-[420px] flex-col rounded-[32px] border border-white/10 bg-white/[0.04] backdrop-blur-sm lg:h-[560px]">
      <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
        <p className="small-label text-slate-400">Ask the docent</p>
        <div className="flex items-center gap-2">
          {mode === "fallback" ? (
            <span
              title={docentCopy.demoNotice}
              className="rounded-full border border-amber-400/40 bg-amber-400/10 px-3 py-1 text-xs font-medium text-amber-300"
            >
              {docentCopy.demoBadge}
            </span>
          ) : null}
          {voice.ttsSupported ? (
            <button
              type="button"
              onClick={voice.toggleVoice}
              aria-pressed={voice.voiceEnabled}
              aria-label={voice.voiceEnabled ? "음성 답변 끄기" : "음성 답변 켜기"}
              title={voice.voiceEnabled ? "음성 답변 켜짐" : "음성 답변 꺼짐"}
              className={
                voice.voiceEnabled
                  ? "inline-flex h-8 w-8 items-center justify-center rounded-full border border-blue-400/50 bg-blue-400/15 text-blue-300"
                  : "inline-flex h-8 w-8 items-center justify-center rounded-full border border-white/15 bg-white/[0.06] text-slate-400 transition-colors hover:text-slate-200"
              }
            >
              {voice.voiceEnabled ? (
                <Volume2 className="h-4 w-4" />
              ) : (
                <VolumeX className="h-4 w-4" />
              )}
            </button>
          ) : null}
        </div>
      </div>

      <div
        ref={listRef}
        onScroll={handleScroll}
        data-lenis-prevent
        className="flex-1 space-y-4 overflow-y-auto px-6 py-6"
      >
        {messages.length === 0 ? (
          <div className="flex h-full flex-col justify-end gap-2">
            <p className="mb-2 text-sm text-slate-400">
              이런 질문으로 시작해 보세요:
            </p>
            {docentStarterQuestions.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => send(q)}
                className="w-fit rounded-full border border-white/15 bg-white/[0.06] px-4 py-2 text-left text-sm text-slate-200 transition-colors hover:border-blue-400/50 hover:bg-blue-400/10"
              >
                {q}
              </button>
            ))}
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {messages.map((message, index) => {
              const isUser = message.role === "user";
              const isLast = index === messages.length - 1;
              const showCaret = isLast && !isUser && isStreaming;
              return (
                <motion.div
                  key={index}
                  initial={reduceMotion ? { opacity: 1 } : { opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25 }}
                  className={isUser ? "flex justify-end" : "flex justify-start"}
                >
                  <div
                    className={
                      isUser
                        ? "max-w-[85%] rounded-2xl rounded-br-md bg-blue-500/90 px-4 py-3 text-sm leading-relaxed text-white"
                        : "max-w-[85%] rounded-2xl rounded-bl-md border border-white/10 bg-white/[0.07] px-4 py-3 text-sm leading-relaxed text-slate-100"
                    }
                  >
                    {message.content || (showCaret ? "" : "…")}
                    {showCaret ? (
                      <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-blue-300 align-middle" />
                    ) : null}
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        )}
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
        className="border-t border-white/10 p-4"
      >
        <div className="flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.06] pl-5 pr-2">
          <input
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder={
              voice.listening ? docentCopy.listeningPlaceholder : docentCopy.inputPlaceholder
            }
            maxLength={docentConfig.maxInputLength}
            disabled={isStreaming || voice.listening}
            className="h-12 flex-1 bg-transparent text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none disabled:opacity-50"
            aria-label="도슨트에게 질문하기"
          />
          {voice.sttSupported ? (
            <button
              type="button"
              onClick={handleMic}
              disabled={isStreaming}
              aria-pressed={voice.listening}
              aria-label={voice.listening ? "음성 입력 중지" : "음성으로 질문하기"}
              className={
                voice.listening
                  ? "inline-flex h-9 w-9 animate-pulse items-center justify-center rounded-full bg-red-500 text-white"
                  : "inline-flex h-9 w-9 items-center justify-center rounded-full border border-white/15 bg-white/[0.06] text-slate-300 transition-colors hover:text-white disabled:opacity-30"
              }
            >
              <Mic className="h-4 w-4" />
            </button>
          ) : null}
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            aria-label="질문 보내기"
            className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-blue-500 text-white transition-opacity disabled:opacity-30"
          >
            <SendHorizontal className="h-4 w-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
