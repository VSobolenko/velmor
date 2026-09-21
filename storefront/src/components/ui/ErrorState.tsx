import type { ReactNode } from "react";
import { StatePanel, type StateHeadingLevel } from "./EmptyState";

export type ErrorStateProps = {
  title: string;
  description?: string;
  /** The retry control. A failure with no way to try again is a dead end. */
  action?: ReactNode;
  illustration?: ReactNode;
  headingLevel?: StateHeadingLevel;
  className?: string;
};

/**
 * The failure member of the state family. It is the same panel as the empty state on a card
 * surface rather than the muted band, so a page that cannot load still looks designed.
 */
export function ErrorState({
  title,
  description,
  action,
  illustration,
  headingLevel,
  className,
}: ErrorStateProps) {
  return (
    <StatePanel
      tone="error"
      title={title}
      description={description}
      action={action}
      illustration={illustration}
      headingLevel={headingLevel}
      className={className}
    />
  );
}
