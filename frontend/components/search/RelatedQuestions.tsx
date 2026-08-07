"use client";

import { ArrowRight } from "lucide-react";
import { motion } from "framer-motion";

interface RelatedQuestionsProps {
  questions: string[];
  onAskQuestion?: (question: string) => void;
}

export default function RelatedQuestions({
  questions,
  onAskQuestion,
}: RelatedQuestionsProps) {
  if (!questions || questions.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2, duration: 0.3 }}
      className="mt-4 space-y-2"
    >
      <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/50 px-1">
        Related questions
      </p>
      <div className="flex flex-col gap-1.5">
        {questions.map((q, i) => (
          <motion.button
            key={i}
            type="button"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.25 + i * 0.07, duration: 0.25 }}
            onClick={() => onAskQuestion?.(q)}
            className="
              group flex items-center gap-2 w-full text-left
              rounded-xl border border-border/50 bg-muted/20
              px-3 py-2.5 text-sm text-muted-foreground
              hover:border-primary/40 hover:bg-primary/5 hover:text-primary
              transition-all duration-150
              focus-visible:ring-2 focus-visible:ring-ring outline-none
            "
          >
            <ArrowRight className="size-3.5 shrink-0 text-muted-foreground/40 group-hover:text-primary transition-all duration-150 group-hover:translate-x-0.5" />
            <span>{q}</span>
          </motion.button>
        ))}
      </div>
    </motion.div>
  );
}
