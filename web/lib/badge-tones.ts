import { cva } from "class-variance-authority";

/**
 * Small shared style helper so every semantic badge in the app (score,
 * verdict, grounding, coverage) draws from the same palette instead of each
 * component inventing its own colors.
 */
export const toneBadge = cva(
  "inline-flex w-fit shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap",
  {
    variants: {
      tone: {
        emerald: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
        amber: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
        rose: "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300",
        blue: "bg-blue-100 text-blue-800 dark:bg-blue-500/15 dark:text-blue-300",
        gray: "bg-muted text-muted-foreground",
      },
    },
    defaultVariants: { tone: "gray" },
  }
);

export type Tone = "emerald" | "amber" | "rose" | "blue" | "gray";
