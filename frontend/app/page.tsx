"use client";

import { useCallback, useEffect, useState } from "react";
import { LogOut, Plus } from "lucide-react";

import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ui/conversation";
import { Message, MessageContent } from "@/components/ui/message";
import { Orb } from "@/components/ui/orb";
import { Response } from "@/components/ui/response";
import {
  SearchBar,
  ResponsePackageCard,
  RelatedQuestions,
} from "@/components/search";
import { ApiError, SearchResponse, searchKnowledgeBase } from "@/lib/api-client";
import { clearToken, getToken, isTokenExpired } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import ThumbsFeedback from "@/components/feedback/ThumbsFeedback";
import LoginForm from "@/components/auth/LoginForm";

interface UserMessage {
  id: string;
  role: "user";
  content: string;
}

interface AssistantMessage {
  id: string;
  role: "assistant";
  isLoading: boolean;
  error: string | null;
  response: SearchResponse | null;
}

type ChatMessage = UserMessage | AssistantMessage;

const STORAGE_KEY = "hexa_chat_history";

function newId() {
  return "msg_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

const STARTER_QUESTIONS = [
  "What are the mortgage approval requirements?",
  "What is the maximum debt to income ratio?",
  "What credit score do I need for the best rate?",
  "How much down payment is required for a conventional loan?",
];

export default function HomePage() {
  const [token, setToken] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Restore auth + transcript on mount.
  useEffect(() => {
    const stored = getToken();
    if (stored && !isTokenExpired(stored)) {
      setToken(stored);
    } else {
      clearToken();
    }
    const saved = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
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

      const userMsg: UserMessage = { id: newId(), role: "user", content: query };
      const assistantMsg: AssistantMessage = {
        id: newId(),
        role: "assistant",
        isLoading: true,
        error: null,
        response: null,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);

      try {
        const result = await searchKnowledgeBase(query, activeToken);
        replaceAssistant(assistantMsg.id, { isLoading: false, response: result });
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
          error: err instanceof Error ? err.message : "Something went wrong",
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

  const handleLoginSuccess = () => {
    setToken(getToken());
    setMessages([]);
    if (typeof window !== "undefined") window.localStorage.removeItem(STORAGE_KEY);
  };

  const handleLogout = () => {
    clearToken();
    setToken(null);
    setMessages([]);
    if (typeof window !== "undefined") window.localStorage.removeItem(STORAGE_KEY);
  };

  const handleNewChat = () => {
    setMessages([]);
    if (typeof window !== "undefined") window.localStorage.removeItem(STORAGE_KEY);
  };

  if (!authChecked) {
    return null;
  }

  if (!token) {
    return <LoginForm onSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="border-b border-border px-4 py-3 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">Hexta</h1>
          <p className="text-xs text-muted-foreground">Mortgage Knowledge Assistant</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={handleNewChat} aria-label="New chat">
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">New chat</span>
          </Button>
          <Button variant="ghost" size="sm" onClick={handleLogout} aria-label="Sign out">
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Sign out</span>
          </Button>
        </div>
      </header>

      <main className="flex-1 overflow-hidden">
        <div className="max-w-3xl mx-auto h-full px-4 py-6">
          <Conversation>
            <ConversationContent>
              {messages.length === 0 ? (
                <ConversationEmptyState>
                  <div className="flex flex-col items-center gap-3">
                    <Orb className="size-12" />
                    <div className="space-y-1">
                      <h3 className="text-sm font-medium">Ask me about mortgage lending</h3>
                      <p className="text-muted-foreground text-sm">
                        I can help you find information about credit scores, LTV ratios,
                        required documents, loan eligibility, debt-to-income rules, and
                        more — all sourced from our internal knowledge base. I do not
                        fabricate answers.
                      </p>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2 justify-center">
                      {STARTER_QUESTIONS.map((q) => (
                        <Button
                          key={q}
                          variant="outline"
                          size="sm"
                          className="max-w-xs text-left text-wrap"
                          onClick={() => {
                            void handleSearch(q);
                          }}
                        >
                          {q}
                        </Button>
                      ))}
                    </div>
                  </div>
                </ConversationEmptyState>
              ) : (
                messages.map((msg) =>
                  msg.role === "user" ? (
                    <Message from="user" key={msg.id}>
                      <MessageContent>
                        <Response>{msg.content}</Response>
                      </MessageContent>
                    </Message>
                  ) : (
                    <Message from="assistant" key={msg.id}>
                      <MessageContent>
                        {msg.isLoading ? (
                          <div className="flex items-center gap-2 text-muted-foreground text-sm">
                            <Orb className="size-6" agentState="listening" />
                            <span>Searching the knowledge base…</span>
                          </div>
                        ) : msg.error ? (
                          <p className="text-sm text-red-600">{msg.error}</p>
                        ) : msg.response ? (
                          <>
                            <ResponsePackageCard
                              title={msg.response.title}
                              excerpts={msg.response.excerpts}
                              confidence={msg.response.confidence}
                              routing={msg.response.routing}
                            />
                            {msg.response.excerpts.length > 0 && (
                              <div className="mt-2">
                                <ThumbsFeedback
                                  responseId={msg.response.response_id}
                                  token={token}
                                />
                              </div>
                            )}
                            <RelatedQuestions
                              questions={msg.response.related_questions}
                              onAskQuestion={handleAskRelated}
                            />
                          </>
                        ) : null}
                      </MessageContent>
                      <div className="ring-border size-8 overflow-hidden rounded-full ring-1">
                        <Orb
                          className="h-full w-full"
                          agentState={msg.isLoading ? "talking" : null}
                        />
                      </div>
                    </Message>
                  )
                )
              )}
            </ConversationContent>
            <ConversationScrollButton />
          </Conversation>
        </div>
      </main>

      <footer className="border-t border-border p-4">
        <div className="max-w-3xl mx-auto">
          <SearchBar
            onSearch={handleSearch}
            isLoading={isLoading}
            placeholder="Ask about mortgage requirements, documents, rates..."
          />
        </div>
      </footer>
    </div>
  );
}
