"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { ArrowUp, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface SearchBarProps {
  onSearch: (query: string) => void;
  isLoading?: boolean;
  placeholder?: string;
  className?: string;
}

const MAX_LEN = 500;

export default function SearchBar({
  onSearch,
  isLoading = false,
  placeholder = "Ask about mortgage requirements, documents, rates…",
  className,
}: SearchBarProps) {
  const [query, setQuery] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-focus on mount
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  // Auto-resize textarea (max ~4 rows)
  const resize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 140) + "px";
  }, []);

  useEffect(() => {
    resize();
  }, [query, resize]);

  const handleSubmit = () => {
    const trimmed = query.trim();
    if (trimmed && !isLoading) {
      onSearch(trimmed);
      setQuery("");
      // Reset height
      if (textareaRef.current) textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const remaining = MAX_LEN - query.length;
  const nearLimit = remaining <= 80;

  return (
    <div className={cn("relative", className)}>
      <div
        className={cn(
          "relative flex items-end gap-2 rounded-2xl border bg-card px-4 py-3",
          "transition-all duration-200",
          "border-border/80",
          "focus-within:border-primary/60 focus-within:shadow-lg",
          "focus-within:shadow-primary/10",
          isLoading && "opacity-70"
        )}
      >
        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={query}
          onChange={(e) => {
            if (e.target.value.length <= MAX_LEN) setQuery(e.target.value);
            resize();
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={isLoading}
          rows={1}
          maxLength={MAX_LEN}
          autoComplete="off"
          aria-label="Ask a question about mortgage lending"
          style={{ resize: "none", overflow: "hidden" }}
          className="
            flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground/50
            focus:outline-none leading-relaxed min-h-[24px] py-0
            disabled:cursor-not-allowed
          "
        />

        {/* Actions row */}
        <div className="flex items-center gap-2 pb-0.5 shrink-0">
          {/* Character count */}
          {query.length > 0 && (
            <span
              className={cn(
                "text-[10px] font-medium tabular-nums transition-colors duration-200",
                nearLimit ? "text-amber-500" : "text-muted-foreground/40"
              )}
            >
              {remaining}
            </span>
          )}

          {/* Send button */}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!query.trim() || isLoading}
            aria-label="Send message"
            title="Send (Enter)"
            className={cn(
              "flex size-8 items-center justify-center rounded-xl transition-all duration-200",
              "focus-visible:ring-2 focus-visible:ring-ring outline-none",
              query.trim() && !isLoading
                ? "gradient-brand text-white hover:opacity-90 hover:shadow-md hover:shadow-primary/30 active:scale-95"
                : "bg-muted text-muted-foreground cursor-not-allowed"
            )}
          >
            {isLoading ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <ArrowUp className="size-4" />
            )}
          </button>
        </div>
      </div>

      {/* Keyboard hint */}
      <p className="mt-1.5 text-center text-[10px] text-muted-foreground/40 select-none">
        <kbd className="font-mono">Enter</kbd> to send ·{" "}
        <kbd className="font-mono">Shift + Enter</kbd> for new line
      </p>
    </div>
  );
}