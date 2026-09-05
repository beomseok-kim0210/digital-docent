"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { docentConfig, docentCopy } from "@/data/docent";
import type {
  DocentChatMessage,
  DocentEmotion,
  DocentMode,
  DocentStreamEvent,
} from "@/types/docent";

interface UseDocentChatOptions {
  onEmotion: (emotion: DocentEmotion) => void;
}

export interface DocentChatState {
  messages: DocentChatMessage[];
  isStreaming: boolean;
  mode: DocentMode | null;
  send: (text: string) => void;
}

export function useDocentChat({ onEmotion }: UseDocentChatOptions): DocentChatState {
  const [messages, setMessages] = useState<DocentChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [mode, setMode] = useState<DocentMode | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  const send = useCallback(
    (text: string) => {
      const question = text.trim();
      if (!question || abortRef.current) return;

      const history: DocentChatMessage[] = [
        ...messages,
        { role: "user" as const, content: question },
      ].slice(-docentConfig.maxHistoryMessages);

      setMessages((prev) => [
        ...prev,
        { role: "user", content: question },
        { role: "assistant", content: "" },
      ]);
      setIsStreaming(true);
      onEmotion("thinking"); // meta 도착 전까지 고민하는 표정

      const appendToAssistant = (delta: string) =>
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          next[next.length - 1] = { ...last, content: last.content + delta };
          return next;
        });

      const failAssistant = () => {
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = {
            role: "assistant",
            content: docentCopy.errorBubble,
          };
          return next;
        });
        onEmotion("sad");
      };

      const controller = new AbortController();
      abortRef.current = controller;

      (async () => {
        try {
          const res = await fetch("/api/docent/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ messages: history }),
            signal: controller.signal,
          });
          if (!res.ok || !res.body) {
            failAssistant();
            return;
          }

          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";

          const handleLine = (raw: string) => {
            if (!raw.trim()) return;
            let event: DocentStreamEvent;
            try {
              event = JSON.parse(raw) as DocentStreamEvent;
            } catch {
              return;
            }
            switch (event.type) {
              case "meta":
                setMode(event.mode);
                onEmotion(event.emotion);
                break;
              case "delta":
                appendToAssistant(event.text);
                break;
              case "error":
                failAssistant();
                break;
              case "done":
                break;
            }
          };

          for (;;) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() ?? "";
            lines.forEach(handleLine);
          }
          if (buffer) handleLine(buffer);
        } catch (err) {
          if (!(err instanceof DOMException && err.name === "AbortError")) {
            failAssistant();
          }
        } finally {
          abortRef.current = null;
          setIsStreaming(false);
        }
      })();
    },
    [messages, onEmotion]
  );

  return { messages, isStreaming, mode, send };
}
