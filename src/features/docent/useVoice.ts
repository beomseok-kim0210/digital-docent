"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  estimateCharsPerSecond,
  textToVisemeTimeline,
  visemeAt,
  type VisemeKey,
  type VisemeTimeline,
} from "@/lib/docent/visemes";

// Web Speech API 타입 (TS 표준 lib에 없어 최소한만 선언)
interface SpeechRecognitionResultEvent {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
}
interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionResultEvent) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

function getSpeechRecognition(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/** TTS로 읽기 좋게 마크다운·이모지류 제거. */
function toSpeakable(text: string): string {
  return text
    .replace(/[*_`#>]/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, "")
    .trim();
}

const SPEECH_RATE = 1.05;

export interface VoiceState {
  sttSupported: boolean;
  ttsSupported: boolean;
  listening: boolean;
  ttsSpeaking: boolean;
  voiceEnabled: boolean;
  /** 현재 발음 중인 입모양. 말하고 있지 않으면 null. */
  viseme: VisemeKey | null;
  toggleVoice: () => void;
  startListening: (onTranscript: (text: string) => void) => void;
  stopListening: () => void;
  speak: (text: string) => void;
  stopSpeaking: () => void;
}

export function useVoice(): VoiceState {
  const [sttSupported, setSttSupported] = useState(false);
  const [ttsSupported, setTtsSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [ttsSpeaking, setTtsSpeaking] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [viseme, setViseme] = useState<VisemeKey | null>(null);

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const frameRef = useRef<number | null>(null);
  // 립싱크 진행 상태: onboundary가 실제 위치를 알려주고, 그 사이는 추정 속도로 보간
  const trackRef = useRef<{
    timeline: VisemeTimeline;
    charsPerSecond: number;
    anchorChar: number;
    anchorTime: number;
  } | null>(null);

  const stopVisemeLoop = useCallback(() => {
    if (frameRef.current !== null) {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }
    trackRef.current = null;
    setViseme(null);
  }, []);

  useEffect(() => {
    setSttSupported(Boolean(getSpeechRecognition()));
    setTtsSupported(typeof window !== "undefined" && "speechSynthesis" in window);
    return () => {
      recognitionRef.current?.abort();
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const startListening = useCallback(
    (onTranscript: (text: string) => void) => {
      const Recognition = getSpeechRecognition();
      if (!Recognition || recognitionRef.current) return;

      // 듣는 동안 TTS는 멈춘다 (에코 방지)
      window.speechSynthesis?.cancel();
      setTtsSpeaking(false);
      stopVisemeLoop();

      const recognition = new Recognition();
      recognition.lang = "ko-KR";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.onresult = (event) => {
        const transcript = event.results[0]?.[0]?.transcript?.trim();
        if (transcript) onTranscript(transcript);
      };
      recognition.onend = () => {
        recognitionRef.current = null;
        setListening(false);
      };
      recognition.onerror = () => {
        recognitionRef.current = null;
        setListening(false);
      };

      recognitionRef.current = recognition;
      setListening(true);
      recognition.start();
    },
    [stopVisemeLoop]
  );

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  const speak = useCallback(
    (text: string) => {
      if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
      const synth = window.speechSynthesis;
      synth.cancel();
      stopVisemeLoop();

      const speakable = toSpeakable(text);
      if (!speakable) return;

      const utterance = new SpeechSynthesisUtterance(speakable);
      const isKorean = /[가-힣]/.test(speakable);
      utterance.lang = isKorean ? "ko-KR" : "en-US";
      const voices = synth.getVoices();
      const preferred = voices.find((v) =>
        v.lang.startsWith(isKorean ? "ko" : "en")
      );
      if (preferred) utterance.voice = preferred;
      utterance.rate = SPEECH_RATE;

      const timeline = textToVisemeTimeline(speakable);

      // 매 프레임 현재 문자 위치를 추정해 입모양을 갱신한다.
      const tick = () => {
        const track = trackRef.current;
        if (!track) return;
        const elapsed = (performance.now() - track.anchorTime) / 1000;
        const charIndex = track.anchorChar + elapsed * track.charsPerSecond;
        setViseme(visemeAt(track.timeline, charIndex));
        frameRef.current = requestAnimationFrame(tick);
      };

      utterance.onstart = () => {
        setTtsSpeaking(true);
        trackRef.current = {
          timeline,
          charsPerSecond: estimateCharsPerSecond(speakable, SPEECH_RATE),
          anchorChar: 0,
          anchorTime: performance.now(),
        };
        frameRef.current = requestAnimationFrame(tick);
      };

      // 단어 경계마다 실제 위치를 받아 추정 오차를 보정하고, 관측된 속도로 갱신
      utterance.onboundary = (event) => {
        const track = trackRef.current;
        if (!track || typeof event.charIndex !== "number") return;
        const now = performance.now();
        const elapsed = (now - track.anchorTime) / 1000;
        if (elapsed > 0.15 && event.charIndex > track.anchorChar) {
          const observed = (event.charIndex - track.anchorChar) / elapsed;
          // 관측값에 천천히 수렴시켜 튀는 것을 막는다
          track.charsPerSecond = track.charsPerSecond * 0.6 + observed * 0.4;
        }
        track.anchorChar = event.charIndex;
        track.anchorTime = now;
      };

      const finish = () => {
        setTtsSpeaking(false);
        stopVisemeLoop();
      };
      utterance.onend = finish;
      utterance.onerror = finish;

      synth.speak(utterance);
    },
    [stopVisemeLoop]
  );

  const stopSpeaking = useCallback(() => {
    window.speechSynthesis?.cancel();
    setTtsSpeaking(false);
    stopVisemeLoop();
  }, [stopVisemeLoop]);

  const toggleVoice = useCallback(() => {
    setVoiceEnabled((prev) => {
      if (prev) window.speechSynthesis?.cancel();
      return !prev;
    });
    setTtsSpeaking(false);
    stopVisemeLoop();
  }, [stopVisemeLoop]);

  return {
    sttSupported,
    ttsSupported,
    listening,
    ttsSpeaking,
    voiceEnabled,
    viseme,
    toggleVoice,
    startListening,
    stopListening,
    speak,
    stopSpeaking,
  };
}
