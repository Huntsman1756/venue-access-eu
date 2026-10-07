"use client";

import { Moon, Sun } from "lucide-react";

/**
 * Theme toggle. The initial theme is applied before paint by an inline
 * script in the root layout; this button only flips the class and persists
 * the choice. Both icons are rendered and CSS picks the visible one, so no
 * client state is needed to stay hydration-safe.
 */
export function ThemeToggle() {
  function toggle() {
    const next = !document.documentElement.classList.contains("dark");
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  }

  return (
    <button
      onClick={toggle}
      aria-label="Toggle color theme"
      className="rounded-md border border-border p-1.5 text-muted-foreground hover:text-foreground"
    >
      <Sun size={14} className="hidden dark:block" aria-hidden />
      <Moon size={14} className="dark:hidden" aria-hidden />
    </button>
  );
}
