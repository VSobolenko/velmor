import { classNames } from "@/components/ui/classes";

/*
 * The mark: a stamped frame, a woven lattice and a filled corner.
 *
 * The geometry is computed here rather than traced from a drawing tool, so the weave is
 * demonstrably even and symmetric:
 *
 *   - The frame's stroke is centred on its path, so the path is inset by half the stroke and
 *     the outside of the stroke lands on the edge of the viewBox.
 *   - The weave is drawn inside a square inset from the frame's inner edge by half of its own
 *     stroke, so no weave stroke overlaps the frame.
 *   - Each family is three parallel lines at one diagonal. A family is symmetric about the
 *     centre, and the spacing between its lines is half the square's diagonal span in the
 *     line's offset from the centre (10 for a 20 unit square). That spacing divides the span
 *     into four equal bands, and at it the outermost lines of the two families meet exactly at
 *     the mid-point of the four sides: the six lines map onto themselves under a quarter turn,
 *     so the lattice reads the same from every direction.
 */

const VIEW_BOX = 24;
const FRAME_STROKE = 1.5;
const FRAME_RADIUS = 1.5;
const WEAVE_STROKE = 1;
const REGISTER_SIZE = 4;
const REGISTER_ORIGIN = 16;

/** Half the frame stroke: the frame path is inset by this much. */
const FRAME_INSET = FRAME_STROKE / 2;
const FRAME_SIDE = VIEW_BOX - FRAME_STROKE;

/** Half the weave stroke: the clearance that keeps a weave stroke off the frame. */
const WEAVE_CLEARANCE = WEAVE_STROKE / 2;

/**
 * The square the weave is drawn inside. The frame's path is inset by half its stroke, so the
 * frame's inner edge sits one whole stroke width from the viewBox edge; the weave then starts
 * half a weave stroke inside that, which is what keeps the two forms off each other.
 */
const WEAVE_MIN = FRAME_STROKE + WEAVE_CLEARANCE;
const WEAVE_MAX = VIEW_BOX - WEAVE_MIN;
const WEAVE_SPAN = WEAVE_MAX - WEAVE_MIN;

/** Three lines per family: the centre line, and one half a span to either side of it. */
const WEAVE_OFFSET = WEAVE_SPAN / 2;
const WEAVE_OFFSETS: readonly number[] = [-WEAVE_OFFSET, 0, WEAVE_OFFSET];

type Point = readonly [number, number];
type Segment = readonly [Point, Point];

/**
 * The two ends of one weave line, as a chord of the weave square.
 *
 * `direction` is 1 for a line descending to the right and -1 for one rising to it; `offset` is
 * how far the line sits from the centre of the square. Each candidate is the line's crossing
 * with one of the four sides; the crossings are deduplicated, because a line through a corner
 * meets it twice, and exactly two distinct ones fall inside the square, which are the ends of
 * the chord. Every value is a whole number or a half, so the comparison is exact.
 */
function weaveSegment(direction: 1 | -1, offset: number): Segment {
  const candidates: readonly Point[] =
    direction === 1
      ? [
          [WEAVE_MIN, WEAVE_MIN - offset],
          [WEAVE_MIN + offset, WEAVE_MIN],
          [WEAVE_MAX, WEAVE_MAX - offset],
          [WEAVE_MAX + offset, WEAVE_MAX],
        ]
      : [
          [WEAVE_MIN, VIEW_BOX + offset - WEAVE_MIN],
          [VIEW_BOX + offset - WEAVE_MIN, WEAVE_MIN],
          [WEAVE_MAX, VIEW_BOX + offset - WEAVE_MAX],
          [VIEW_BOX + offset - WEAVE_MAX, WEAVE_MAX],
        ];
  const inside = candidates.filter(
    ([x, y]) => x >= WEAVE_MIN && x <= WEAVE_MAX && y >= WEAVE_MIN && y <= WEAVE_MAX,
  );
  /* A line through a corner of the square meets it twice, so the crossings are deduplicated. */
  const distinct = inside.filter(
    ([x, y], index) =>
      inside.findIndex(([otherX, otherY]) => otherX === x && otherY === y) === index,
  );
  return [distinct[0], distinct[1]];
}

/** The six weave lines: three descending, three rising. */
const WEAVE_LINES: readonly Segment[] = [
  ...WEAVE_OFFSETS.map((offset) => weaveSegment(1, offset)),
  ...WEAVE_OFFSETS.map((offset) => weaveSegment(-1, offset)),
];

export type HallmarkProps = {
  size?: number;
  /** The mark's meaning, for a mark that stands for something. Omit it for decoration. */
  title?: string;
  className?: string;
};

/**
 * The hallmark: the device that marks a verified thing. It appears beside a verified statement
 * and as a section rule, never on a control, a button or a price.
 *
 * It is drawn in `currentColor`, so the caller sets the colour from the token set with a text
 * utility and the mark follows the surface it is placed on.
 */
export function Hallmark({ size = 24, title, className }: HallmarkProps) {
  const labelled = title !== undefined;
  return (
    <svg
      aria-hidden={labelled ? undefined : true}
      className={classNames("shrink-0", className)}
      fill="none"
      height={size}
      role={labelled ? "img" : undefined}
      stroke="currentColor"
      strokeWidth={FRAME_STROKE}
      viewBox={`0 0 ${VIEW_BOX} ${VIEW_BOX}`}
      width={size}
      xmlns="http://www.w3.org/2000/svg"
    >
      {labelled ? <title>{title}</title> : null}
      <rect
        height={FRAME_SIDE}
        rx={FRAME_RADIUS}
        width={FRAME_SIDE}
        x={FRAME_INSET}
        y={FRAME_INSET}
      />
      {WEAVE_LINES.map(([[x1, y1], [x2, y2]]) => (
        <line
          key={`${x1}:${y1}:${x2}:${y2}`}
          strokeWidth={WEAVE_STROKE}
          x1={x1}
          x2={x2}
          y1={y1}
          y2={y2}
        />
      ))}
      <rect
        fill="currentColor"
        height={REGISTER_SIZE}
        stroke="none"
        width={REGISTER_SIZE}
        x={REGISTER_ORIGIN}
        y={REGISTER_ORIGIN}
      />
    </svg>
  );
}
