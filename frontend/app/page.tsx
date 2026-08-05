"use client";

import { useCallback, useEffect, useState } from "react";
import { LogOut } from "lucide-react";
import {
  SearchBar,
  ResponsePackageCard,
  RelatedQuestions,
} from "@/components/search";
import { ApiError, searchKnowledgeBase, SearchResponse } from "@/lib/api-client";
import { clearToken, getToken, isTokenExpired } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import ThumbsFeedback from "@/components/feedback/ThumbsFeedback";
import LoginForm from "@/components/auth/LoginForm";

export default function HomePage() {
  const [token, setToken] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const stored = getToken();
    if (stored && isTokenExpired(stored)) {
      clearToken();
      setToken(null);
    } else {
      setToken(stored);
    }
    setAuthChecked(true);
  }, []);

  const handleSearch = useCallback(
    async (q: string) => {
      const activeToken = getToken();
      if (!activeToken || isTokenExpired(activeToken)) {
        clearToken();
        setToken(null);
        return;
      }
      setToken(activeToken);
      setIsLoading(true);
      setError(null);

      try {
        const result = await searchKnowledgeBase(q, activeToken);
        setResponse(result);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          setToken(null);
          setResponse(null);
          setError(null);
          return;
        }
        setError(err instanceof Error ? err.message : "Something went wrong");
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const handleAskRelated = useCallback(
    (question: string) => {
      handleSearch(question);
    },
    [handleSearch]
  );

  const handleLogout = () => {
    clearToken();
    setToken(null);
    setResponse(null);
    setError(null);
  };

  const handleLoginSuccess = () => {
    setToken(getToken());
    setResponse(null);
    setError(null);
  };

  if (!authChecked) {
    return null;
  }

  if (!token) {
    return <LoginForm onSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border py-4">
        <div className="max-w-4xl mx-auto px-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Hexta</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Mortgage Knowledge Assistant
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleLogout}
            aria-label="Sign out"
          >
            <LogOut />
            Sign out
          </Button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {!response && !isLoading && (
          <div className="mt-12 text-center">
            <h2 className="text-3xl font-bold text-foreground mb-2">
              Ask me about mortgage lending
            </h2>
            <p className="text-muted-foreground mb-8 max-w-2xl mx-auto">
              I can help you find information about credit scores, LTV ratios,
              required documents, loan eligibility, and more — all from our
              internal knowledge base.
            </p>
          </div>
        )}

        <div className="mt-8">
          <SearchBar
            onSearch={handleSearch}
            isLoading={isLoading}
            placeholder="e.g., What is the minimum credit score for a VA loan?"
          />
        </div>

        {error && (
          <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800 text-center">
            {error}
          </div>
        )}

        {response && (
          <>
            <ResponsePackageCard
              title={response.title}
              excerpts={response.excerpts}
              confidence={response.confidence}
              routing={response.routing}
            />
            <ThumbsFeedback responseId={response.response_id} token={token} />
            <RelatedQuestions
              questions={response.related_questions}
              onAskQuestion={handleAskRelated}
            />
          </>
        )}
      </main>

      <footer className="border-t border-border py-6 mt-12">
        <div className="max-w-4xl mx-auto px-4 text-center text-sm text-muted-foreground">
          Hexta — Mortgage Knowledge Assistant. All responses are sourced from
          internal documents.
        </div>
      </footer>
    </div>
  );
}