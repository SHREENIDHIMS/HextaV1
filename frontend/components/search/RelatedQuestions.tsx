"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

interface RelatedQuestionsProps {
  questions: string[];
  onAskQuestion?: (question: string) => void;
}

export default function RelatedQuestions({
  questions,
  onAskQuestion,
}: RelatedQuestionsProps) {
  const [expanded, setExpanded] = useState(true);

  if (!questions || questions.length === 0) return null;

  return (
    <div className="mt-6 border-t border-border pt-4 space-y-3">
      <Button
        type="button"
        variant="ghost"
        className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground p-1 h-auto"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? (
          <ChevronUp className="w-4 h-4" />
        ) : (
          <ChevronDown className="w-4 h-4" />
        )}
        Related Questions ({questions.length})
      </Button>

      {expanded && (
        <div className="space-y-2 pt-1">
          {questions.map((q, i) => (
            <div key={i}>
              <Button
                type="button"
                variant="ghost"
                className="block w-full text-left p-2.5 text-sm rounded-lg border border-border hover:bg-muted/50 transition-colors whitespace-normal"
                onClick={() => onAskQuestion?.(q)}
              >
                {q}
              </Button>
              {i < questions.length - 1 && <Separator className="my-1" />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
