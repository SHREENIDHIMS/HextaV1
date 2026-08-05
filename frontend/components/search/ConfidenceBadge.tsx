"use client";

import { Shield, TrendingUp, AlertCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ConfidenceBadgeProps {
  confidence: number;
  routing: "answer" | "partial" | "no_answer";
  size?: "sm" | "md" | "lg";
}

export default function ConfidenceBadge({
  confidence,
  routing,
  size = "md",
}: ConfidenceBadgeProps) {
  const sizeClasses = {
    sm: "text-xs",
    md: "text-sm",
    lg: "text-base",
  };

  const getIcon = () => {
    switch (routing) {
      case "answer":
        return <Shield className="w-3.5 h-3.5" />;
      case "partial":
        return <TrendingUp className="w-3.5 h-3.5" />;
      case "no_answer":
        return <AlertCircle className="w-3.5 h-3.5" />;
      default:
        return <Shield className="w-3.5 h-3.5" />;
    }
  };

  const getVariant = () => {
    switch (routing) {
      case "answer":
        return "default";
      case "partial":
        return "outline";
      case "no_answer":
        return "secondary";
      default:
        return "outline";
    }
  };

  const colorClass = {
    answer:
      "bg-green-100 text-green-800 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-900/50",
    partial:
      "bg-yellow-100 text-yellow-800 border-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-300 dark:border-yellow-900/50",
    no_answer:
      "bg-muted text-muted-foreground border-border dark:bg-muted/50",
  }[routing];

  const label = {
    answer: "High Confidence",
    partial: "Partial Answer",
    no_answer: "No Answer Found",
  }[routing] ?? "Uncertain";

  return (
    <Badge
      variant={getVariant() as "default" | "secondary" | "outline"}
      className={cn("rounded-full gap-1 font-medium", sizeClasses[size], colorClass)}
    >
      {getIcon()}
      <span>{Math.round(confidence)}%</span>
      <span className="mx-1 opacity-60">·</span>
      <span>{label}</span>
    </Badge>
  );
}
