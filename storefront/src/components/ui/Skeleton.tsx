import { classNames } from "./classes";

type Props = {
  className?: string;
};

/**
 * A placeholder block for a page that is still loading. It is hidden from assistive
 * technology on purpose: the announcement belongs to the page, which knows what it is
 * waiting for and in which locale.
 *
 * The caller supplies the shape through `className`, so a skeleton holds the geometry of the
 * thing it stands in for. `motion-reduce:animate-none` makes that explicit rather than
 * relying on the global reduced-motion override.
 */
export function Skeleton({ className }: Props) {
  return (
    <div
      aria-hidden="true"
      className={classNames(
        "animate-pulse rounded-sm bg-surface-sunken motion-reduce:animate-none",
        className,
      )}
    />
  );
}
