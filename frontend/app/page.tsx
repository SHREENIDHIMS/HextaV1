"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertCircle } from "lucide-react";

import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ui/conversation";
import Sidebar from "@/components/ui/sidebar";
import { Message, MessageContent } from "@/components/ui/message";
import { Orb } from "@/components/ui/orb";
import { Response } from "@/components/ui/response";
import AssistantActions from "@/components/ui/AssistantActions";
import UserActions from "@/components/ui/UserActions";
import {
  SearchBar,
  ResponsePackageCard,
  RelatedQuestions,
} from "@/components/search";
import { ApiError, SearchResponse, searchKnowledgeBase } from "@/lib/api-client";
import { clearToken, getToken, isTokenExpired } from "@/lib/auth";
import LoginForm from "@/components/auth/LoginForm";

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
      <Orb className="h-full w-full" agentState={talking ? "talking" : null} />
    </div>
  );
}

function LoadingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center gap-3 py-2"
    >
      <Orb className="size-5 shrink-0" agentState="listening" />
      <div className="flex items-center gap-1.5">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="block size-1.5 rounded-full bg-primary"
            animate={{ opacity: [0.3, 1, 0.3], y: [0, -4, 0] }}
            transition={{
              repeat: Infinity,
              duration: 0.9,
              delay: i * 0.18,
              ease: "easeInOut",
            }}
          />
        ))}
        <span className="text-xs text-muted-foreground ml-1">
          Searching knowledge base…
        </span>
      </div>
    </motion.div>
  );
}

export default function HomePage() {
  const [token, setToken] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [openSources, setOpenSources] = useState<Record<string, boolean>>({});

  // Restore auth + transcript on mount.
  useEffect(() => {
    const stored = getToken();
    if (stored && !isTokenExpired(stored)) {
      setToken(stored);
    } else {
      clearToken();
    }
    const saved =
      typeof window !== "undefined"
        ? window.localStorage.getItem(STORAGE_KEY)
        : null;
    if (saved) {
      try {
        setMessages(JSON.parse(saved));
      } catch {
        // ignore corrupted transcript
      }
    }
    setAuthChecked(true);
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
      const activeToken = getToken();
      if (!activeToken || isTokenExpired(activeToken)) {
        clearToken();
        setToken(null);
        return;
      }
      setToken(activeToken);
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
        const result = await searchKnowledgeBase(query, activeToken);
        replaceAssistant(assistantMsg.id, {
          isLoading: false,
          response: result,
        });
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
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
    [replaceAssistant]
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
    setToken(getToken());
    setMessages([]);
    if (typeof window !== "undefined")
      window.localStorage.removeItem(STORAGE_KEY);
  };

  const handleLogout = () => {
    clearToken();
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
      <Sidebar onSignOut={handleLogout} onNewChat={handleNewChat} />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <main className="relative flex min-h-0 flex-1 overflow-hidden">
          <Conversation className="scrollbar h-full flex-1">
            <ConversationContent>
              <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col px-4 py-6 sm:px-6">
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
                          <h2 className="text-2xl font-bold gradient-brand-text">
                            Mortgage Knowledge Assistant
                          </h2>
                          <p className="text-sm text-muted-foreground leading-relaxed">
                            Ask me anything about mortgage lending — credit
                            scores, LTV ratios, required documents, loan
                            eligibility, and more. Every answer comes directly
                            from your knowledge base.
                          </p>
                        </div>

                        {/* Starter questions */}
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
                    <div key="messages" className="space-y-2">
                      {messages.map((msg) =>
                        msg.role === "user" ? (
                          <Message from="user" key={msg.id} timestamp={msg.ts}>
                            <MessageContent>
                              <Response>{msg.content}</Response>
                            </MessageContent>
                            <UserActions text={msg.content} />
                          </Message>
                        ) : (
                          <Message
                            from="assistant"
                            key={msg.id}
                            timestamp={msg.ts}
                          >
                            <MessageContent>
                              {msg.isLoading ? (
                                <LoadingIndicator />
                              ) : msg.error ? (
                                <motion.div
                                  initial={{ opacity: 0 }}
                                  animate={{ opacity: 1 }}
                                  className="flex items-start gap-2 rounded-xl border border-destructive/20 bg-destructive/5 p-3"
                                >
                                  <AlertCircle className="size-4 text-destructive shrink-0 mt-0.5" />
                                  <p className="text-sm text-destructive">
                                    {msg.error}
                                  </p>
                                </motion.div>
                              ) : msg.response ? (
                                <>
                                  <ResponsePackageCard
                                    title={msg.response.title}
                                    excerpts={msg.response.excerpts}
                                    confidence={msg.response.confidence}
                                    routing={msg.response.routing}
                                    sourcesOpen={openSources[msg.id]}
                                    onToggleSources={() =>
                                      toggleSources(msg.id)
                                    }
                                  />
                                  <AssistantActions
                                    answerText={answerTextFor(msg)}
                                    responseId={msg.response.response_id}
                                    token={token}
                                    userQuery={msg.userQuery}
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
                            <AssistantAvatar talking={msg.isLoading} />
                          </Message>
                        )
                      )}
                    </div>
                  )}
                </AnimatePresence>
              </div>
            </ConversationContent>
            <ConversationScrollButton />
          </Conversation>
        </main>

        {/* Footer input */}
        <footer className="border-t border-border/60 bg-background/80 backdrop-blur-sm">
          <div className="mx-auto w-full max-w-3xl px-4 py-4 sm:px-6">
            <SearchBar
              onSearch={handleSearch}
              isLoading={isLoading}
              placeholder="Ask about mortgage requirements, documents, rates…"
            />
          </div>
        </footer>
      </div>
    </div>
  );
}
