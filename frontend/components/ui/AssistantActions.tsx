"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  BookOpen,
  Check,
  Copy,
  Pause,
  Play,
  RefreshCw,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { motion } from "framer-motion";

import { cn } from "@/lib/utils";
import { submitFeedback, ApiError } from "@/lib/api-client";

interface AssistantActionsProps {
  answerText: string;
  responseId: string;
  token: string | null;
  userQuery?: string;
  onRegenerate?: (query: string) => void;
  sourcesOpen?: boolean;
  onToggleSources?: () => void;
}

type FeedbackRating = 1 | -1 | null;

function useSpeech() {
  const [speaking, setSpeaking] = useState(false);
  const cancelledRef = useRef(false);

  useEffect(
    () => () => {
      if (typeof window !== "undefined" && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    },
    []
  );

  const speak = useCallback(
    (text: string) => {
      if (typeof window === "undefined" || !window.speechSynthesis) return false;
      window.speechSynthesis.cancel();
      cancelledRef.current = false;
      const utter = new SpeechSynthesisUtterance(text);
      utter.onend = () => {
        if (!cancelledRef.current) setSpeaking(false);
      };
      window.speechSynthesis.speak(utter);
      setSpeaking(true);
      return true;
    },
    [cancelledRef]
  );

  const stop = useCallback(() => {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      cancelledRef.current = true;
      window.speechSynthesis.cancel();
      setSpeaking(false);
    }
  }, [cancelledRef]);

  return { speaking, speak, stop };
}

interface ActionBtnProps {
  onClick: () => void;
  disabled?: boolean;
  label: string;
  active?: boolean;
  activeClass?: string;
  children: React.ReactNode;
}

function ActionBtn({
  onClick,
  disabled,
  label,
  active,
  activeClass,
  children,
}: ActionBtnProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className={cn(
        "group/btn relative flex size-7 items-center justify-center rounded-lg transition-all duration-150",
        "text-muted-foreground hover:text-foreground hover:bg-muted/80",
        "focus-visible:ring-2 focus-visible:ring-ring outline-none",
        "disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent",
        active && activeClass
      )}
    >
      {children}
      {/* Tooltip */}
      <span className="absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md bg-popover border border-border/60 px-2 py-1 text-[10px] text-popover-foreground shadow-md opacity-0 group-hover/btn:opacity-100 transition-opacity duration-150 pointer-events-none z-50">
        {label}
      </span>
    </button>
  );
}

export default function AssistantActions({
  answerText,
  responseId,
  token,
  userQuery,
  onRegenerate,
  sourcesOpen,
  onToggleSources,
}: AssistantActionsProps) {
  const { speaking, speak, stop } = useSpeech();
  const [copied, setCopied] = useState(false);
  const [rating, setRating] = useState<FeedbackRating>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(answerText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard may be unavailable in some contexts
    }
  }, [answerText]);

  const handleRate = useCallback(
    async (next: FeedbackRating) => {
      if (!token || next === null || rating !== null) return;
      setError(null);
      setSubmitting(true);
      try {
        await submitFeedback({ response_id: responseId, rating: next }, token);
        setRating(next);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          setError("Session expired. Please sign in again.");
        } else {
          setError(err instanceof Error ? err.message : "Feedback failed");
        }
      } finally {
        setSubmitting(false);
      }
    },
    [responseId, token, rating]
  );

  const handleReadAloud = () => {
    if (speaking) stop();
    else speak(answerText);
  };

  const handleRegenerate = () => {
    if (userQuery && onRegenerate) onRegenerate(userQuery);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15, duration: 0.25 }}
      className="mt-2 flex items-center gap-0.5"
    >
      {/* Copy */}
      <ActionBtn onClick={handleCopy} label={copied ? "Copied!" : "Copy answer"}>
        {copied ? (
          <Check className="size-3.5 text-green-500" />
        ) : (
          <Copy className="size-3.5" />
        )}
      </ActionBtn>

      {/* Read aloud */}
      <ActionBtn
        onClick={handleReadAloud}
        disabled={!answerText}
        label={speaking ? "Stop reading" : "Read aloud"}
        active={speaking}
        activeClass="text-primary bg-primary/10"
      >
        {speaking ? (
          <Pause className="size-3.5" />
        ) : (
          <Play className="size-3.5" />
        )}
      </ActionBtn>

      {/* Regenerate */}
      <ActionBtn
        onClick={handleRegenerate}
        disabled={!userQuery || onRegenerate == null}
        label="Regenerate"
      >
        <RefreshCw className="size-3.5" />
      </ActionBtn>

      {/* Divider */}
      <div className="mx-1 h-4 w-px bg-border/60" />

      {/* Thumbs up */}
      <ActionBtn
        onClick={() => handleRate(1)}
        disabled={submitting || rating !== null}
        label="Good response"
        active={rating === 1}
        activeClass="text-green-500 bg-green-500/10"
      >
        {rating === 1 ? (
          <motion.span
            initial={{ scale: 0.5 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 400, damping: 15 }}
          >
            <ThumbsUp className="size-3.5 fill-current" />
          </motion.span>
        ) : (
          <ThumbsUp className="size-3.5" />
        )}
      </ActionBtn>

      {/* Thumbs down */}
      <ActionBtn
        onClick={() => handleRate(-1)}
        disabled={submitting || rating !== null}
        label="Bad response"
        active={rating === -1}
        activeClass="text-red-400 bg-red-400/10"
      >
        {rating === -1 ? (
          <motion.span
            initial={{ scale: 0.5 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 400, damping: 15 }}
          >
            <ThumbsDown className="size-3.5 fill-current" />
          </motion.span>
        ) : (
          <ThumbsDown className="size-3.5" />
        )}
      </ActionBtn>

      {/* Sources toggle */}
      {onToggleSources != null && (
        <>
          <div className="mx-1 h-4 w-px bg-border/60" />
          <ActionBtn
            onClick={onToggleSources}
            label={sourcesOpen ? "Hide sources" : "View sources"}
            active={sourcesOpen}
            activeClass="text-primary bg-primary/10"
          >
            <BookOpen className="size-3.5" />
          </ActionBtn>
        </>
      )}

      {error && (
        <span role="alert" className="ml-2 text-xs text-red-400">
          {error}
        </span>
      )}
    </motion.div>
  );
}
