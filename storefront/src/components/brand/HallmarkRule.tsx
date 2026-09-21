import { classNames } from "@/components/ui/classes";
import { Hallmark } from "./Hallmark";

/*
 * The rule: a hairline across the full width with one hallmark centred on it, which is how a
 * section is divided in this identity - not with a bare border.
 *
 * The hairline spans the whole width and the mark is drawn over it on paper, so the line reads
 * as passing behind the mark rather than stopping at it.
 */

const MARK_SIZE = 20;
const MARK_CLASSES = "bg-paper px-3 text-accent";

export type HallmarkRuleProps = {
  className?: string;
};

/**
 * A decorative divider: it carries no text and no meaning of its own, so it is hidden from
 * assistive technology. The mark is in the accent, the hairline is in the line colour, and the
 * background it is drawn on is paper.
 */
export function HallmarkRule({ className }: HallmarkRuleProps) {
  return (
    <div aria-hidden="true" className={classNames("relative w-full", className)}>
      <span className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-line" />
      <div className="relative flex justify-center">
        <span className={MARK_CLASSES}>
          <Hallmark className="block" size={MARK_SIZE} />
        </span>
      </div>
    </div>
  );
}
