"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertCircle } from "lucide-react";

import { ConversationEmptyState } from "@/components/ui/conversation";
import Sidebar from "@/components/ui/sidebar";
import { Message, MessageContent } from "@/components/ui/message";
import { Orb } from "@/components/ui/orb";
import { Response } from "@/components/ui/response";
import AssistantActions from "@/components/ui/AssistantActions";
import UserActions from "@/components/ui/UserActions";
import TypingIndicator from "@/components/chat/TypingIndicator";
import {
  SearchBar,
  ResponsePackageCard,
  RelatedQuestions,
} from "@/components/search";
import { ApiError, SearchResponse, searchKnowledgeBase } from "@/lib/api-client";
import { clearSession, getSession, signOut } from "@/lib/auth";
import LoginForm from "@/components/auth/LoginForm";
import { tokens } from "@/lib/tokens";

interface UserMessage {
  id: string;
  role: "user";
  content: string;
  ts: number;
}

interface AssistantMessage {
  id: string;
  role: "assistant";
  isLoading: boolean;
  error: string | null;
  response: SearchResponse | null;
  ts: number;
  userQuery?: string;
}

type ChatMessage = UserMessage | AssistantMessage;

const STORAGE_KEY = "hexa_chat_history";

// D6 (documented decision): the transcript is persisted client-side in
// localStorage so a reload restores the conversation on a static export.
// It is NOT encrypted; it is cleared on logout/new chat/login. Acceptable
// for internal use, but avoid persisting sensitive loan data — re-examine
// if transcripts will contain PII.

function newId() {
  return "msg_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

const STARTER_QUESTIONS = [
  { q: "What are the mortgage approval requirements?", emoji: "🏠" },
  { q: "What is the maximum debt-to-income ratio?", emoji: "📊" },
  { q: "What credit score do I need for the best rate?", emoji: "⭐" },
  { q: "How much down payment is required for a conventional loan?", emoji: "💰" },
];

function AssistantAvatar({ talking }: { talking: boolean }) {
  return (
    <div className="flex size-7 shrink-0 items-center justify-center overflow-hidden rounded-full ring-1 ring-border/80 bg-card">
      <Orb className="h-full w-full" agentState={talking ? "talking" : "listening"} />
    </div>
  );
}

export default function HomePage() {
  const [token, setToken] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [openSources, setOpenSources] = useState<Record<string, boolean>>({});
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // Restore auth + transcript on mount.
  useEffect(() => {
    let cancelled = false;
    void getSession().then((session) => {
      if (cancelled) return;
      if (session) {
        setToken("active");
      } else {
        clearSession();
      }
      // Wait for the cookie verification so a logged-in user doesn't flash
      // the login screen on reload.
      setAuthChecked(true);
    });
    const saved =
      typeof window !== "undefined"
        ? window.localStorage.getItem(STORAGE_KEY)
        : null;
    if (saved) {
      try {
        setMessages(JSON.parse(saved));
      } catch {
        /* ignore corrupted transcript */
      }
    }
    return () => {
      cancelled = true;
    };
  }, []);

  // Persist transcript on every change (while authenticated).
  useEffect(() => {
    if (token && typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    }
  }, [messages, token]);

  const replaceAssistant = useCallback(
    (id: string, patch: Partial<Omit<AssistantMessage, "role">>) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.role === "assistant" && m.id === id ? { ...m, ...patch } : m
        )
      );
    },
    []
  );

  const handleSearch = useCallback(
    async (query: string) => {
      if (!token) {
        setToken(null);
        return;
      }
      setIsLoading(true);

      const userMsg: UserMessage = {
        id: newId(),
        role: "user",
        content: query,
        ts: Date.now(),
      };
      const assistantMsg: AssistantMessage = {
        id: newId(),
        role: "assistant",
        isLoading: true,
        error: null,
        response: null,
        ts: Date.now(),
        userQuery: query,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);

      try {
        const result = await searchKnowledgeBase(query);
        replaceAssistant(assistantMsg.id, {
          isLoading: false,
          response: result,
        });
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          clearSession();
          setToken(null);
          replaceAssistant(assistantMsg.id, {
            isLoading: false,
            error: "Session expired. Please sign in again.",
          });
          return;
        }
        replaceAssistant(assistantMsg.id, {
          isLoading: false,
          error:
            err instanceof Error ? err.message : "Something went wrong",
        });
      } finally {
        setIsLoading(false);
      }
    },
    [replaceAssistant, token]
  );

  const handleAskRelated = useCallback(
    (question: string) => {
      void handleSearch(question);
    },
    [handleSearch]
  );

  const handleRegenerate = useCallback(
    (query: string) => {
      void handleSearch(query);
    },
    [handleSearch]
  );

  const answerTextFor = (msg: AssistantMessage): string =>
    msg.response?.excerpts?.map((e) => e.text).join("\n\n") ?? "";

  const toggleSources = (id: string) =>
    setOpenSources((prev) => ({ ...prev, [id]: !prev[id] }));

  const handleLoginSuccess = () => {
    // The login response set the httpOnly cookie; confirm the session so
    // the cached identity (role/email) is available to sidebar & actions.
    void getSession().then((s) => setToken(s ? "active" : null));
    setMessages([]);
    if (typeof window !== "undefined")
      window.localStorage.removeItem(STORAGE_KEY);
  };

  const handleLogout = () => {
    void signOut();
    setToken(null);
    setMessages([]);
    if (typeof window !== "undefined")
      window.localStorage.removeItem(STORAGE_KEY);
  };

  const handleNewChat = () => {
    setMessages([]);
    if (typeof window !== "undefined")
      window.localStorage.removeItem(STORAGE_KEY);
  };

  if (!authChecked) return null;
  if (!token) return <LoginForm onSuccess={handleLoginSuccess} />;

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar
        onSignOut={handleLogout}
        onNewChat={handleNewChat}
        mobileOpen={isSidebarOpen}
        onMobileOpen={() => setIsSidebarOpen(true)}
        onMobileClose={() => setIsSidebarOpen(false)}
      />

      <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* Message list */}
        <div className="flex-1 overflow-y-auto scrollbar pb-[120px]">
          <div
            className="mx-auto flex w-full max-w-[50rem] flex-col px-4 py-6 sm:px-6"
            style={{ maxWidth: tokens.maxWidth.chat }}
          >
            <AnimatePresence mode="wait">
              {messages.length === 0 ? (
                <ConversationEmptyState key="empty">
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.4, ease: "easeOut" }}
                    className="flex flex-col items-center gap-6 text-center"
                  >
                    {/* Animated Orb */}
                    <motion.div
                      animate={{
                        y: [0, -8, 0],
                      }}
                      transition={{
                        duration: 3,
                        repeat: Infinity,
                        ease: "easeInOut",
                      }}
                    >
                      <Orb className="size-20" />
                    </motion.div>

                    {/* Headline */}
                    <div className="space-y-2 max-w-md">
                      <h2 className="text-3xl font-bold gradient-brand-text">
                        Mortgage Knowledge Assistant
                      </h2>
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        Ask me anything about mortgage lending — credit
                        scores, LTV ratios, required documents, loan
                        eligibility, and more. Every answer comes directly
                        from your knowledge base.
                      </p>
                    </div>

                    {/* Starter questions as quick-prompt chips */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg mt-2">
                      {STARTER_QUESTIONS.map(({ q, emoji }, i) => (
                        <motion.button
                          key={q}
                          type="button"
                          initial={{ opacity: 0, y: 12 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{
                            delay: 0.15 + i * 0.08,
                            duration: 0.3,
                          }}
                          onClick={() => void handleSearch(q)}
                          className="
                            group flex items-start gap-2.5 rounded-xl
                            border border-border/60 bg-card p-3
                            text-left text-sm text-muted-foreground
                            hover:border-primary/40 hover:bg-primary/5 hover:text-foreground
                            transition-all duration-200
                            focus-visible:ring-2 focus-visible:ring-ring outline-none
                          "
                        >
                          <span className="text-lg leading-none">{emoji}</span>
                          <span className="leading-snug">{q}</span>
                        </motion.button>
                      ))}
                    </div>
                  </motion.div>
                </ConversationEmptyState>
              ) : (
                <div key="messages" className="space-y-1">
                  {messages.map((msg) =>
                    msg.role === "user" ? (
                        <Message from="user" key={msg.id} timestamp={msg.ts}>
                        <MessageContent className="is-user">
                          <Response>{msg.content}</Response>
                          <UserActions text={msg.content} />
                        </MessageContent>
                      </Message>
                    ) : (
                      <Message
                        from="assistant"
                        key={msg.id}
                        timestamp={msg.ts}
                      >
                        <AssistantAvatar talking={msg.isLoading} />
                        <MessageContent className="is-assistant">
                          {msg.isLoading ? (
                            <TypingIndicator />
                          ) : msg.error ? (
                            <motion.div
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                              className="flex items-start gap-3 rounded-xl border border-error/20 bg-error/5 p-3"
                            >
                              <AlertCircle className="size-4 text-error shrink-0 mt-0.5" />
                              <p className="text-sm text-error">
                                {msg.error}
                              </p>
                            </motion.div>
                          ) : msg.response ? (
                            <>
                              <ResponsePackageCard
                                excerpts={msg.response.excerpts}
                                routing={msg.response.routing}
                                sourcesOpen={openSources[msg.id]}
                              />
                              <AssistantActions
                                answerText={answerTextFor(msg)}
                                responseId={msg.response.response_id}
                                userQuery={msg.userQuery}
                                confidence={msg.response.confidence}
                                routing={msg.response.routing}
                                onRegenerate={handleRegenerate}
                                sourcesOpen={openSources[msg.id]}
                                onToggleSources={() =>
                                  toggleSources(msg.id)
                                }
                              />
                              <RelatedQuestions
                                questions={msg.response.related_questions}
                                onAskQuestion={handleAskRelated}
                              />
                            </>
                          ) : null}
                        </MessageContent>
                      </Message>
                    )
                  )}
                </div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Fixed bottom-center search bar — ChatGPT/Claude style */}
        <div className="fixed bottom-0 left-0 right-0 z-50 flex justify-center pb-4 pointer-events-none">
          <div
            className="pointer-events-auto"
            style={{ maxWidth: `calc(${typeof tokens.maxWidth.chat === "number" ? tokens.maxWidth.chat : "50rem"} + 2rem)` }}
          >
            <SearchBar
              onSearch={handleSearch}
              isLoading={isLoading}
              placeholder="Ask about mortgage requirements, documents, rates…"
            />
          </div>
        </div>
      </main>
    </div>
  );
}
