import { classNames } from "@/components/ui/classes";

/*
 * The medallion: the same construction as `Hallmark`, reduced to one form for a size where the
 * weave could not be read. It is the glyph the wordmark puts in place of an `o`.
 *
 * The ring's stroke is centred on its path, so the radius is half the viewBox less half the
 * stroke. The cross is the weave's own two directions - 45 degrees and -45 degrees - so the
 * medallion and the mark share one angle; it is drawn inside a radius reduced by half of the
 * ring's stroke and half of its own, so the two forms stay clear of each other, and its stems
 * are chords of that inner circle, which is why every end is `inner / sqrt(2)` from the centre.
 */

const VIEW_BOX = 24;
const CENTRE = VIEW_BOX / 2;
const RING_STROKE = 1.5;
const CROSS_STROKE = 1;

/** The ring, then the cross: the light between them is half of each stroke. */
const RADIUS = CENTRE - RING_STROKE / 2;
const INNER_RADIUS = RADIUS - RING_STROKE / 2 - CROSS_STROKE / 2;
const CROSS_REACH = INNER_RADIUS / Math.SQRT2;

const CROSS_LINES: readonly (readonly [number, number, number, number])[] = [
  [
    CENTRE - CROSS_REACH,
    CENTRE - CROSS_REACH,
    CENTRE + CROSS_REACH,
    CENTRE + CROSS_REACH,
  ],
  [
    CENTRE - CROSS_REACH,
    CENTRE + CROSS_REACH,
    CENTRE + CROSS_REACH,
    CENTRE - CROSS_REACH,
  ],
];

export type HallmarkMedallionProps = {
  size?: number;
  /** The medallion's meaning, for a medallion that stands for something. Omit it for decoration. */
  title?: string;
  className?: string;
};

/**
 * The hallmark in its medallion form, drawn in `currentColor` like `Hallmark`. It exists so the
 * wordmark does not depend on an outline drawing of the letters.
 */
export function HallmarkMedallion({ size = 24, title, className }: HallmarkMedallionProps) {
  const labelled = title !== undefined;
  return (
    <svg
      aria-hidden={labelled ? undefined : true}
      className={classNames("shrink-0", className)}
      fill="none"
      height={size}
      role={labelled ? "img" : undefined}
      stroke="currentColor"
      strokeWidth={RING_STROKE}
      viewBox={`0 0 ${VIEW_BOX} ${VIEW_BOX}`}
      width={size}
      xmlns="http://www.w3.org/2000/svg"
    >
      {labelled ? <title>{title}</title> : null}
      <circle cx={CENTRE} cy={CENTRE} r={RADIUS} />
      {CROSS_LINES.map(([x1, y1, x2, y2]) => (
        <line
          key={`${x1}:${y1}:${x2}:${y2}`}
          strokeWidth={CROSS_STROKE}
          x1={x1}
          x2={x2}
          y1={y1}
          y2={y2}
        />
      ))}
    </svg>
  );
}
