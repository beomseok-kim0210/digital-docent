"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import type { DocentEmotion } from "@/types/docent";
import { ChatPanel } from "./ChatPanel";
import { useDocentChat } from "./useDocentChat";
import { useVoice } from "./useVoice";

const AvatarCanvas = dynamic(() => import("./AvatarCanvas"), {
  ssr: false,
  loading: () => <AvatarSkeleton />,
});

function AvatarSkeleton() {
  return (
    <div className="relative h-[42vh] min-h-[300px] w-full overflow-hidden rounded-[32px] bg-[radial-gradient(ellipse_at_center,rgba(59,130,246,0.15),rgba(11,17,32,0.6))] lg:h-[560px]">
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="h-3 w-3 animate-pulse rounded-full bg-blue-400/70" />
      </div>
    </div>
  );
}

export function DocentExperience() {
  const [emotion, setEmotion] = useState<DocentEmotion>("neutral");
  const chat = useDocentChat({ onEmotion: setEmotion });
  const voice = useVoice();

  // 스트리밍이 끝나면 (음성 모드일 때) 마지막 도슨트 답변을 낭독한다.
  const spokenCountRef = useRef(0);
  useEffect(() => {
    if (chat.isStreaming || !voice.voiceEnabled) return;
    const last = chat.messages[chat.messages.length - 1];
    if (
      last?.role === "assistant" &&
      last.content &&
      chat.messages.length > spokenCountRef.current
    ) {
      spokenCountRef.current = chat.messages.length;
      voice.speak(last.content);
    }
  }, [chat.isStreaming, chat.messages, voice]);

  return (
    <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
      <AvatarCanvas emotion={emotion} viseme={voice.viseme} />
      <ChatPanel {...chat} voice={voice} />
    </div>
  );
}
