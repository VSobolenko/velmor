import Link from "next/link";
import { classNames } from "@/components/ui/classes";
import { HallmarkMedallion } from "./HallmarkMedallion";

export type WordmarkSize = "sm" | "md" | "lg";

export type WordmarkProps = {
  name: string;
  /** The `lang` of the text, so a screen reader pronounces the name in the buyer's language. */
  locale: string;
  /** The home page for the active locale, taken from the route rather than built here. */
  href: string;
  size?: WordmarkSize;
  className?: string;
};

/** The identity's display steps: the wordmark is a display element, so it uses those. */
const SIZE_CLASSES: Record<WordmarkSize, string> = {
  sm: "text-2xl",
  md: "text-3xl",
  lg: "text-4xl",
};

/** The glyph a medallion stands in for. */
const MEDALLION_GLYPH = "o";

/**
 * The medallion against the glyph it replaces. The circle is a little taller than the lowercase
 * glyph of the display face, so the ring stays legible where the wordmark is small; it is set in
 * `em` rather than in pixels, so a caller that changes the font size keeps the two in step.
 */
const MEDALLION_CLASSES = "col-start-1 row-start-1 h-[0.62em] w-[0.62em] justify-self-center";

/** The glyph the medallion is drawn over: laid out and copied, but not painted. */
const GLYPH_CLASSES = "col-start-1 row-start-1 opacity-0";

/** One run of the name, or one medallion. */
type Piece =
  | { readonly key: string; readonly kind: "text"; readonly value: string }
  | { readonly key: string; readonly kind: "glyph" };

/**
 * The name split around every `o` it contains, so a medallion can stand in the glyph's place.
 *
 * No shape of name is special-cased: a name with no `o` yields text only and renders as plain
 * text, and a name with more than two yields a medallion for each one it has.
 */
function piecesFor(name: string): readonly Piece[] {
  const parts = name.split(MEDALLION_GLYPH);
  const pieces: Piece[] = [];
  parts.forEach((part, index) => {
    if (index > 0) {
      pieces.push({ key: `glyph-${index}`, kind: "glyph" });
    }
    if (part !== "") {
      pieces.push({ key: `text-${index}`, kind: "text", value: part });
    }
  });
  return pieces;
}

/**
 * The brand name, set in the display face with a medallion in place of every `o` in it.
 *
 * The accessible name is the plain brand name, carried once by the visually hidden span rather
 * than by `aria-label` on the link. An `aria-label` replaces the link's content as a name, so
 * the name would exist only in the accessibility tree: a translation engine, a reader that
 * walks the text content, or a selection would not find it. Keeping the name as real text means
 * one source for the announced name and the copied one, and it cannot drift from `name`.
 *
 * The visible arrangement is the same string, with the `o` glyphs unpainted and a medallion
 * drawn over each of them, so a buyer who selects the wordmark copies the name rather than the
 * fragments the medallions interrupt. It is `aria-hidden`, so the name is not announced twice
 * and the fragments are never announced at all.
 */
export function Wordmark({ name, locale, href, size = "md", className }: WordmarkProps) {
  return (
    <Link
      className={classNames(
        "tap-target inline-flex items-center font-heading font-semibold tracking-tight",
        SIZE_CLASSES[size],
        className,
      )}
      href={href}
      lang={locale}
    >
      <span aria-hidden="true">
        {piecesFor(name).map((piece) =>
          piece.kind === "text" ? (
            <span key={piece.key}>{piece.value}</span>
          ) : (
            <span className="inline-grid items-baseline" key={piece.key}>
              <span className={GLYPH_CLASSES}>{MEDALLION_GLYPH}</span>
              <HallmarkMedallion className={MEDALLION_CLASSES} />
            </span>
          ),
        )}
      </span>
      {/* `select-none` keeps the hidden copy out of a selection, so copying the visible name
          does not yield it twice. */}
      <span className="sr-only select-none">{name}</span>
    </Link>
  );
}
