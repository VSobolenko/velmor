import type { ReactNode } from "react";
import { classNames } from "./classes";

export type StateTone = "empty" | "error";
export type StateHeadingLevel = 1 | 2 | 3;

export type StatePanelProps = {
  /**
   * Decorative by contract: the heading and the body carry the meaning, so the artwork is
   * kept out of the accessibility tree rather than announced as a second, vaguer label.
   */
  illustration?: ReactNode;
  title: string;
  description?: string;
  /** The single way out of the state. */
  action?: ReactNode;
  tone?: StateTone;
  /**
   * The level the heading takes in the page outline. An empty listing sits below a page
   * title at level 2; the not-found route is the page title and needs level 1.
   */
  headingLevel?: StateHeadingLevel;
  className?: string;
};

/**
 * The shape every "there is nothing here, and here is what to do" surface shares: an optional
 * plate, a heading, a body and one action. An empty listing, a failed fetch and an unknown
 * route differ in copy and tone, not in layout.
 */
export function StatePanel({
  illustration,
  title,
  description,
  action,
  tone = "empty",
  headingLevel = 2,
  className,
}: StatePanelProps) {
  const Heading = `h${headingLevel}` as "h1" | "h2" | "h3";
  return (
    <div
      className={classNames(
        "flex flex-col items-center gap-3 rounded-lg border border-line px-gutter-lg py-section text-center",
        tone === "error" ? "bg-surface" : "bg-surface-muted",
        className,
      )}
    >
      {illustration === undefined ? null : (
        <div
          aria-hidden="true"
          className="flex min-h-24 items-center justify-center"
        >
          {illustration}
        </div>
      )}
      <Heading className="text-balance font-heading text-xl font-semibold text-ink">
        {title}
      </Heading>
      {description === undefined ? null : (
        <p className="max-w-prose text-sm text-muted">{description}</p>
      )}
      {action === undefined ? null : <div className="pt-1">{action}</div>}
    </div>
  );
}

export type EmptyStateProps = {
  title: string;
  description?: string;
  /** The way out of the state: a link back to the catalogue, a clear-filters button. */
  action?: ReactNode;
  illustration?: ReactNode;
  headingLevel?: StateHeadingLevel;
  className?: string;
};

export function EmptyState({
  title,
  description,
  action,
  illustration,
  headingLevel,
  className,
}: EmptyStateProps) {
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
