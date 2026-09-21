import type { ReactNode } from "react";
import { StatePanel, type StateHeadingLevel } from "./EmptyState";

export type NotFoundStateProps = {
  title: string;
  description?: string;
  /** The way back: a link to the shop or the catalogue. */
  action?: ReactNode;
  illustration?: ReactNode;
  headingLevel?: StateHeadingLevel;
  className?: string;
};

/**
 * The unknown-route member of the state family. It shares the panel with the empty state
 * so a mistyped URL lands on the same surface as any other absence.
 */
export function NotFoundState({
  title,
  description,
  action,
  illustration,
  headingLevel,
  className,
}: NotFoundStateProps) {
  return (
    <StatePanel
      title={title}
      description={description}
      action={action}
      illustration={illustration}
      headingLevel={headingLevel}
      className={className}
    />
  );
}
