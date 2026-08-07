"use client"

import { cn } from "@/lib/utils"
import { useTheme, type Theme } from "./provider"

const OPTIONS: { value: Theme; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
]

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme()

  return (
    <div
      role="radiogroup"
      aria-label="Color scheme"
      className={cn("inline-flex items-center rounded-md bg-muted p-1", className)}
    >
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={theme === option.value}
          onClick={() => setTheme(option.value)}
          className={cn(
            "flex min-h-11 min-w-11 items-center justify-center rounded px-3 py-2 text-xs font-medium transition-colors",
            theme === option.value
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
