import { Badge } from "@/components/ui/Badge";
import { classNames } from "@/components/ui/classes";
import { Hallmark } from "./Hallmark";

/*
 * The verification cue: the mark beside the licence identity on a good, so a buyer can see at a
 * glance that this item's rights were checked rather than take the surrounding copy on trust.
 *
 * The badge itself is the shared `Badge` on its accent tone - the same component every other
 * badge on a card is built from - so this file contributes the mark and the optional explanatory
 * title and nothing else. The label is the caller's: a licence statement is copy, and copy lives
 * in the locale dictionaries. The wrapped span carries the title attribute, because the shared
 * badge does not take one.
 */

const MARK_SIZE = 14;

export type HallmarkBadgeProps = {
  /** The licence or verification statement, read from the active locale's dictionary. */
  label: string;
  /** An explanation for a pointer, on the badge, for a reader who stops on it. */
  title?: string;
  className?: string;
};

export function HallmarkBadge({ label, className, title }: HallmarkBadgeProps) {
  return (
    <span className={classNames("inline-flex", className)} title={title}>
      <Badge tone="accent">
        <Hallmark size={MARK_SIZE} />
        {label}
      </Badge>
    </span>
  );
}
