"use client";

import { useState } from "react";
import { ChevronRight, FileText, AlertTriangle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

import type { SearchExcerpt } from "@/lib/api-client";
import ConfidenceBadge from "./ConfidenceBadge";

interface ResponsePackageCardProps {
  title: string;
  excerpts: SearchExcerpt[];
  confidence: number;
  routing: "answer" | "partial" | "no_answer";
  sourcesOpen?: boolean;
  onToggleSources?: () => void;
}

const MAX_VISIBLE = 2;

export default function ResponsePackageCard({
  title,
  excerpts,
  confidence,
  routing,
  sourcesOpen,
}: ResponsePackageCardProps) {
  const [showAllExcerpts, setShowAllExcerpts] = useState(false);

  if (routing === "no_answer" || excerpts.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-start gap-3 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4"
      >
        <AlertTriangle className="size-4 text-amber-500 shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-foreground">
            No match found in knowledge base
          </p>
          <p className="text-sm text-muted-foreground mt-0.5">
            Try rephrasing your question or asking about a different topic.
          </p>
        </div>
      </motion.div>
    );
  }

  const visible = excerpts.slice(0, MAX_VISIBLE);
  const hidden = excerpts.slice(MAX_VISIBLE);
  const hasMoreExcerpts = hidden.length > 0;
  const displayed = showAllExcerpts ? excerpts : visible;

  // Deduplicate source documents by title
  const documents = Array.from(
    excerpts
      .reduce((acc, e) => {
        if (!acc.has(e.source.title)) {
          acc.set(e.source.title, e.source.section);
        }
        return acc;
      }, new Map<string, string | null>())
      .entries()
  ).sort(([a], [b]) => a.localeCompare(b));

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="w-full space-y-3"
    >
      {/* Title + confidence */}
      <div className="space-y-2">
        <h3 className="text-base font-semibold text-foreground leading-snug">
          {title}
        </h3>
        <ConfidenceBadge confidence={confidence} routing={routing} size="sm" />
      </div>

      {/* Excerpts */}
      <div className="space-y-2">
        <AnimatePresence initial={false}>
          {displayed.map((excerpt, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06, duration: 0.25 }}
              className="relative rounded-xl border border-border/60 bg-card overflow-hidden"
            >
              {/* Accent bar */}
              <div
                className="absolute left-0 top-0 bottom-0 w-0.5 rounded-l-xl"
                style={{
                  background:
                    routing === "answer"
                      ? "linear-gradient(to bottom, oklch(0.68 0.28 265), oklch(0.60 0.22 290))"
                      : routing === "partial"
                      ? "linear-gradient(to bottom, oklch(0.72 0.20 55), oklch(0.68 0.18 70))"
                      : "oklch(0.60 0.03 265)",
                }}
              />
              <div className="pl-4 pr-4 py-3">
                {excerpt.source.section && (
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60 mb-1">
                    {excerpt.source.section}
                  </p>
                )}
                <p className="whitespace-pre-line text-sm leading-relaxed text-foreground">
                  {excerpt.text}
                </p>
                <p className="mt-1.5 text-[10px] text-muted-foreground/50 flex items-center gap-1">
                  <FileText className="size-3" />
                  {excerpt.source.title}
                </p>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {hasMoreExcerpts && !showAllExcerpts && (
          <button
            type="button"
            onClick={() => setShowAllExcerpts(true)}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-primary transition-colors duration-150 px-1 py-0.5"
            aria-expanded={false}
          >
            <ChevronRight className="size-3.5" />
            Show {hidden.length} more excerpt{hidden.length === 1 ? "" : "s"}
          </button>
        )}
      </div>

      {/* Sources panel */}
      <AnimatePresence>
        {sourcesOpen && (
          <motion.div
            key="sources"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            id="hexa-sources-list"
            role="region"
            aria-label="Sources"
            className="overflow-hidden"
          >
            <div className="mt-1 rounded-xl border border-border/50 bg-muted/30 p-3 space-y-2">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60 mb-2">
                Sources ({documents.length})
              </p>
              {documents.map(([docTitle, section]) => (
                <div key={docTitle} className="flex items-start gap-2 text-sm">
                  <div className="size-5 shrink-0 mt-0.5 rounded bg-primary/10 flex items-center justify-center">
                    <FileText className="size-3 text-primary" />
                  </div>
                  <div className="min-w-0">
                    <span className="font-medium text-foreground text-xs">
                      {docTitle}
                    </span>
                    {section && (
                      <p className="text-[10px] text-muted-foreground">
                        {section}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
