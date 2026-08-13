/* =========================================================
   Design Tokens — central export for TypeScript components.
   Mirrors the CSS custom properties in styles/globals.css.
   ========================================================= */

export const tokens = {
  /* ── Spacing scale (4 / 8 / 12 / 16 / 24 / 32) ── */
  spacing: {
    xs: "0.25rem",   /* 4px  */
    sm: "0.5rem",    /* 8px  */
    md: "0.75rem",   /* 12px */
    base: "1rem",    /* 16px */
    lg: "1.5rem",    /* 24px */
    xl: "2rem",      /* 32px */
  } as const,

  /* ── Type scale ── */
  fontSize: {
    xs: "0.75rem",   /* 12px — captions, metadata */
    sm: "0.875rem",  /* 14px — body, badge labels */
    base: "1rem",    /* 16px — body text */
    lg: "1.125rem",  /* 18px — card titles, source labels */
    xl: "1.25rem",   /* 20px — section headings */
    "2xl": "1.5rem",  /* 24px — page titles */
    "3xl": "1.875rem", /* 30px — H1 chat/page title */
  } as const,

  fontWeight: {
    normal: "400",
    medium: "500",
    semibold: "600",
    bold: "700",
  } as const,

  /* ── Accent (single source of truth — matches --primary) ── */
  accent: "oklch(0.68 0.28 265)", /* electric indigo */

  /* ── Semantic confidence colors ── */
  semantic: {
    success: {
      DEFAULT: "oklch(0.65 0.22 140)",
      foreground: "oklch(0.10 0.03 140)",
      bg: "oklch(0.90 0.18 140)",
      border: "oklch(0.80 0.18 140)",
    },
    warning: {
      DEFAULT: "oklch(0.78 0.16 60)",
      foreground: "oklch(0.15 0.03 60)",
      bg: "oklch(0.95 0.12 60)",
      border: "oklch(0.85 0.12 60)",
    },
    error: {
      DEFAULT: "oklch(0.577 0.245 27.325)",
      foreground: "oklch(0.99 0 0)",
      bg: "oklch(0.95 0.20 25)",
      border: "oklch(0.85 0.20 25)",
    },
  } as const,

  /* ── Border / shadow helpers ── */
  border: {
    default: "var(--border)",
    subtle: "oklch(1 0 0 / 6%)",
  } as const,

  /* ── Max width for chat column ── */
  maxWidth: {
    chat: "50rem", /* 800px */
  } as const,
} as const;

/* Convenience: spacing shorthand */
export const spacing = tokens.spacing;
export const fontSize = tokens.fontSize;
export const fontWeight = tokens.fontWeight;
