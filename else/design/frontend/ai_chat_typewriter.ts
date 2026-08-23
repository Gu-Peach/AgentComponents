// ============================================================
// AI 聊天流式输出 · 打字机效果完整实现
// 技术栈：Fetch + ReadableStream + requestAnimationFrame
// ============================================================

// ─────────────────────────────────────────────────────────────
// 1. useTypewriter Hook
//    输入：完整文本（会随 SSE 流持续增长）
//    输出：当前已"打"出的文本
// ─────────────────────────────────────────────────────────────

// hooks/useTypewriter.ts
import { useState, useEffect, useRef, useCallback } from "react";

interface TypewriterOptions {
  speed?: number;      // 每字符间隔 ms，默认 18
  batchSize?: number;  // 每帧批量显示字符数，默认 1
}

export function useTypewriter(
  fullText: string,
  options: TypewriterOptions = {}
) {
  const { speed = 18, batchSize = 1 } = options;

  const [displayedText, setDisplayedText] = useState("");
  const [isTyping, setIsTyping] = useState(false);

  // 用 ref 持有最新的 fullText，避免 effect 闭包问题
  const fullTextRef = useRef(fullText);
  const rafIdRef = useRef<number>(0);
  const containerRef = useRef<HTMLDivElement>(null); // 用于可见性检测
  const isVisibleRef = useRef(true);

  // 同步最新文本到 ref
  useEffect(() => {
    fullTextRef.current = fullText;
  }, [fullText]);

  // ── 可见性检测：不在视口时直接跳过动画 ──
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        isVisibleRef.current = entries[0].isIntersecting;
        if (!entries[0].isIntersecting) {
          // 离开视口：立即显示全部，取消动画
          cancelAnimationFrame(rafIdRef.current);
          setDisplayedText(fullTextRef.current);
          setIsTyping(false);
        }
      },
      { threshold: 0.1 }
    );
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // ── 核心：RAF 打字机动画循环 ──
  useEffect(() => {
    if (!fullText) {
      setDisplayedText("");
      setIsTyping(false);
      return;
    }

    // 不在视口：直接显示，不做动画
    if (!isVisibleRef.current) {
      setDisplayedText(fullText);
      return;
    }

    let lastTimestamp = 0;
    let accumulatedTime = 0;
    let cancelled = false;

    const animate = (timestamp: number) => {
      if (cancelled) return;

      if (!lastTimestamp) lastTimestamp = timestamp;
      const deltaTime = timestamp - lastTimestamp;
      accumulatedTime += deltaTime;

      if (accumulatedTime >= speed) {
        setDisplayedText((current) => {
          const target = fullTextRef.current; // 始终读最新文本

          // ── 增量续打判断 ──
          // case A：新文本是当前已显示文本的延续 → 从断点继续
          // case B：文本发生了替换（不同消息）→ 清空重新打
          const base = target.startsWith(current) ? current : "";

          const nextChars = target.slice(base.length, base.length + batchSize);
          if (!nextChars) {
            // 已全部显示
            setIsTyping(false);
            return base.length === 0 ? target : current; // base="" 说明要重置
          }

          const newText = base + nextChars;

          // 还有剩余，继续下一帧
          if (newText.length < target.length) {
            rafIdRef.current = requestAnimationFrame(animate);
          } else {
            setIsTyping(false);
          }

          return newText;
        });

        lastTimestamp = timestamp;
        accumulatedTime = 0;
      } else {
        // 时间不够，等下一帧
        rafIdRef.current = requestAnimationFrame(animate);
      }
    };

    setIsTyping(true);
    rafIdRef.current = requestAnimationFrame(animate);

    return () => {
      cancelled = true;
      cancelAnimationFrame(rafIdRef.current);
    };
  }, [fullText, speed, batchSize]);

  // 跳过动画，直接显示全文（用于"跳过"按钮）
  const skipAnimation = useCallback(() => {
    cancelAnimationFrame(rafIdRef.current);
    setDisplayedText(fullTextRef.current);
    setIsTyping(false);
  }, []);

  return { displayedText, isTyping, containerRef, skipAnimation };
}


// ─────────────────────────────────────────────────────────────
// 2. useAgentStream Hook
//    负责 SSE fetch，将流式 token 累积为 fullText
//    fullText 传给 useTypewriter 做打字机渲染
// ─────────────────────────────────────────────────────────────

// hooks/useAgentStream.ts
import { useCallback, useRef } from "react";
import { useAgentStore } from "@/stores/agentStore";

export function useAgentStream(sessionId: string) {
  const { addMessage, updateLastAssistantMessage, setStreaming, isStreaming } =
    useAgentStore();
  const abortControllerRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (content: string) => {
      if (isStreaming) return;

      // 取消上一次未完成的请求
      abortControllerRef.current?.abort();
      const controller = new AbortController();
      abortControllerRef.current = controller;

      // 立即写入用户消息
      addMessage({ role: "user", content, id: crypto.randomUUID() });

      // 写入空 AI 消息占位（fullText 从空开始，随 token 追加）
      const assistantMsgId = crypto.randomUUID();
      addMessage({
        role: "assistant",
        content: "",   // 这里 content 是 fullText，由流追加
        id: assistantMsgId,
      });

      setStreaming(true);

      try {
        const response = await fetch(
          `/api/agent/sessions/${sessionId}/message`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content }),
            signal: controller.signal,
          }
        );

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        if (!response.body) throw new Error("No response body");

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";      // 不完整行的缓冲
        let accumulated = ""; // 已接收的完整文本

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // 按行分割处理 SSE（格式：data: <token>\n\n）
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? ""; // 最后一行可能不完整，留到下次

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const token = line.slice(6);
            if (token === "[DONE]") break;

            accumulated += token;
            // 将累积文本更新到 store（useTypewriter 会持续读最新的）
            updateLastAssistantMessage(assistantMsgId, accumulated);
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        // 错误处理：在消息末尾追加错误提示
        updateLastAssistantMessage(
          assistantMsgId,
          "\n\n⚠️ 请求中断，请重试。"
        );
      } finally {
        setStreaming(false);
      }
    },
    [sessionId, isStreaming, addMessage, updateLastAssistantMessage, setStreaming]
  );

  const abort = useCallback(() => {
    abortControllerRef.current?.abort();
    setStreaming(false);
  }, [setStreaming]);

  return { sendMessage, abort };
}


// ─────────────────────────────────────────────────────────────
// 3. agentStore（Zustand）
// ─────────────────────────────────────────────────────────────

// stores/agentStore.ts
import { create } from "zustand";
import { immer } from "zustand/middleware/immer";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string; // assistant 消息：这是 fullText（完整累积文本）
}

interface AgentState {
  messages: ChatMessage[];
  isStreaming: boolean;
  addMessage: (msg: ChatMessage) => void;
  updateLastAssistantMessage: (id: string, content: string) => void;
  setStreaming: (v: boolean) => void;
  clearMessages: () => void;
}

export const useAgentStore = create<AgentState>()(
  immer((set) => ({
    messages: [],
    isStreaming: false,

    addMessage: (msg) =>
      set((state) => {
        state.messages.push(msg);
      }),

    updateLastAssistantMessage: (id, content) =>
      set((state) => {
        const msg = state.messages.find((m) => m.id === id);
        if (msg) msg.content = content;
      }),

    setStreaming: (v) =>
      set((state) => {
        state.isStreaming = v;
      }),

    clearMessages: () =>
      set((state) => {
        state.messages = [];
      }),
  }))
);


// ─────────────────────────────────────────────────────────────
// 4. StreamMessage 组件
//    消费 message.content（fullText）→ 交给 useTypewriter 渲染
// ─────────────────────────────────────────────────────────────

// components/ai-chat/StreamMessage.tsx
"use client";
import { useTypewriter } from "@/hooks/useTypewriter";
import type { ChatMessage } from "@/stores/agentStore";

interface StreamMessageProps {
  message: ChatMessage;
  isLastAssistant: boolean; // 只有最后一条 assistant 消息才做打字机效果
  speed?: number;
  batchSize?: number;
}

export function StreamMessage({
  message,
  isLastAssistant,
  speed = 18,
  batchSize = 2,
}: StreamMessageProps) {
  const isAssistant = message.role === "assistant";

  // 只有最后一条 assistant 消息启用打字机；历史消息直接显示
  const { displayedText, isTyping, containerRef, skipAnimation } =
    useTypewriter(
      isLastAssistant ? message.content : message.content, // 历史消息 fullText 已固定
      {
        speed: isLastAssistant ? speed : 0,   // speed=0 等效于立即显示
        batchSize: isLastAssistant ? batchSize : 999,
      }
    );

  const isUser = message.role === "user";

  return (
    <div
      className={`flex gap-2 mb-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
    >
      {/* 头像 */}
      <div
        className={`w-6 h-6 rounded-full flex items-center justify-center
          text-[10px] font-bold shrink-0 mt-0.5
          ${isUser ? "bg-[#0078d4] text-white" : "bg-[#3a3a3a] text-[#888]"}`}
      >
        {isUser ? "U" : "AI"}
      </div>

      {/* 消息气泡 */}
      <div
        ref={containerRef}
        className={`relative max-w-[85%] rounded-lg px-3 py-2 text-sm
          leading-relaxed group
          ${isUser
            ? "bg-[#0078d4] text-white"
            : "bg-[#2d2d2d] text-[#ddd] border border-[#3a3a3a]"
          }`}
      >
        {/* 文本内容 */}
        <pre className="whitespace-pre-wrap font-sans text-xs leading-5 m-0">
          {displayedText}
        </pre>

        {/* 打字机光标 */}
        {isTyping && (
          <span
            className="inline-block w-[2px] h-[13px] bg-current
              ml-[1px] -mb-[2px] align-middle
              animate-[cursor-blink_0.8s_ease-in-out_infinite]"
          />
        )}

        {/* 跳过按钮（打字中才显示） */}
        {isTyping && (
          <button
            onClick={skipAnimation}
            className="absolute -bottom-5 right-0 text-[10px] text-[#555]
              hover:text-[#888] transition-colors whitespace-nowrap"
          >
            跳过 ▶▶
          </button>
        )}
      </div>
    </div>
  );
}

// tailwind.config.ts 中需要添加 cursor-blink keyframe：
// extend: {
//   keyframes: {
//     "cursor-blink": {
//       "0%, 100%": { opacity: "1" },
//       "50%": { opacity: "0" },
//     },
//   },
//   animation: {
//     "cursor-blink": "cursor-blink 0.8s ease-in-out infinite",
//   },
// },


// ─────────────────────────────────────────────────────────────
// 5. AIChatPanel 完整组合
// ─────────────────────────────────────────────────────────────

// components/ai-chat/AIChatPanel.tsx
"use client";
import { useRef, useEffect, useState } from "react";
import { Send, Square, Trash2 } from "lucide-react";
import { useAgentStore } from "@/stores/agentStore";
import { useAgentStream } from "@/hooks/useAgentStream";
import { StreamMessage } from "./StreamMessage";

interface AIChatPanelProps {
  sessionId: string;
}

export function AIChatPanel({ sessionId }: AIChatPanelProps) {
  const [input, setInput] = useState("");
  const { messages, isStreaming, clearMessages } = useAgentStore();
  const { sendMessage, abort } = useAgentStream(sessionId);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 新消息到来时滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, messages[messages.length - 1]?.content]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    setInput("");
    // 重置 textarea 高度
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    await sendMessage(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // textarea 自动增高
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
  };

  // 找到最后一条 assistant 消息的 id
  const lastAssistantId = [...messages]
    .reverse()
    .find((m) => m.role === "assistant")?.id;

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] border-t border-[#333]">
      {/* 头部 */}
      <div className="flex items-center justify-between px-3 py-2
        border-b border-[#333] bg-[#252526] shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[#0078d4] animate-pulse" />
          <span className="text-xs text-[#aaa] font-medium">AI 工艺助手</span>
        </div>
        <button
          onClick={clearMessages}
          className="text-[#555] hover:text-[#888] transition-colors"
          title="清空对话"
        >
          <Trash2 size={13} />
        </button>
      </div>

      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1 min-h-0">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full
            text-[#444] text-xs text-center gap-2">
            <span className="text-2xl">🤖</span>
            <p>描述您的工艺需求<br />例如：让机械臂以 8 秒节拍抓取零件</p>
          </div>
        )}

        {messages.map((msg) => (
          <StreamMessage
            key={msg.id}
            message={msg}
            isLastAssistant={msg.id === lastAssistantId}
            speed={16}
            batchSize={2}
          />
        ))}

        {/* 流式加载中但还没有内容时的骨架 */}
        {isStreaming &&
          messages[messages.length - 1]?.role === "user" && (
          <div className="flex gap-2">
            <div className="w-6 h-6 rounded-full bg-[#3a3a3a] shrink-0 mt-0.5" />
            <div className="bg-[#2d2d2d] rounded-lg px-3 py-2 flex gap-1 items-center">
              {[0, 0.2, 0.4].map((delay) => (
                <span
                  key={delay}
                  className="w-1.5 h-1.5 rounded-full bg-[#555]
                    animate-bounce"
                  style={{ animationDelay: `${delay}s` }}
                />
              ))}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* 输入区 */}
      <div className="shrink-0 border-t border-[#333] p-2">
        <div className="flex gap-2 items-end
          bg-[#2d2d2d] rounded-lg border border-[#3a3a3a]
          focus-within:border-[#0078d4] transition-colors px-2 py-1.5">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="描述工艺需求... (Enter 发送，Shift+Enter 换行)"
            rows={1}
            className="flex-1 bg-transparent text-xs text-[#ddd]
              placeholder:text-[#555] resize-none outline-none
              leading-5 min-h-[20px] max-h-[120px]"
          />

          {/* 发送 / 中止按钮 */}
          {isStreaming ? (
            <button
              onClick={abort}
              className="w-6 h-6 rounded flex items-center justify-center
                bg-[#c72e2e] hover:bg-[#e03333] transition-colors shrink-0"
              title="中止生成"
            >
              <Square size={10} className="text-white fill-white" />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              className="w-6 h-6 rounded flex items-center justify-center
                bg-[#0078d4] hover:bg-[#1184db] disabled:opacity-30
                disabled:cursor-not-allowed transition-colors shrink-0"
              title="发送 (Enter)"
            >
              <Send size={10} className="text-white" />
            </button>
          )}
        </div>

        <p className="text-[9px] text-[#444] mt-1 text-center">
          Shift+Enter 换行 · Enter 发送
        </p>
      </div>
    </div>
  );
}
