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

  const iconSizeClasses = {
    sm: "size-3.5",
    md: "size-4",
    lg: "size-4.5",
  };

  const getIcon = () => {
    switch (routing) {
      case "answer":
        return (
          <Shield
            className={cn("text-success", iconSizeClasses[size])}
            aria-hidden="true"
          />
        );
      case "partial":
        return (
          <TrendingUp
            className={cn("text-warning", iconSizeClasses[size])}
            aria-hidden="true"
          />
        );
      case "no_answer":
        return (
          <AlertCircle
            className={cn("text-error", iconSizeClasses[size])}
            aria-hidden="true"
          />
        );
      default:
        return (
          <Shield
            className={cn("text-success", iconSizeClasses[size])}
            aria-hidden="true"
          />
        );
    }
  };

  /* Semantic color classes using centralized tokens */
  const colorClass = {
    answer:
      "bg-success/10 text-success border-success/20",
    partial:
      "bg-warning/10 text-warning border-warning/20",
    no_answer:
      "bg-muted/50 text-muted-foreground border-border",
  }[routing];

  const label = {
    answer: "High Confidence",
    partial: "Partial Answer",
    no_answer: "No Answer Found",
  }[routing] ?? "Uncertain";

  return (
    <Badge
      variant="outline"
      className={cn(
        "rounded-full gap-1.5 font-medium transition-colors",
        sizeClasses[size],
        colorClass
      )}
    >
      {getIcon()}
      <span>{Math.round(confidence)}%</span>
      <span className="mx-1 opacity-60">·</span>
      <span>{label}</span>
    </Badge>
  );
}
