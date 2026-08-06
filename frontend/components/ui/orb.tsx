"use client"

import { cn } from "@/lib/utils"

export type AgentState = null | "thinking" | "listening" | "talking"

export type OrbProps = {
  colors?: [string, string]
  className?: string
  agentState?: AgentState
}

export function Orb({
  colors = ["#CADCFC", "#A0B9D1"],
  className,
  agentState = null,
}: OrbProps) {
  const active = agentState === "talking" || agentState === "listening"
  return (
    <span
      className={cn(
        "relative block size-8 rounded-full ring-1 ring-border transition-opacity",
        active && "animate-pulse",
        agentState === null && "opacity-60",
        className
      )}
      style={{
        backgroundImage: `linear-gradient(180deg, ${colors[0]}, ${colors[1]})`,
      }}
    />
  )
}

Orb.displayName = "Orb"
