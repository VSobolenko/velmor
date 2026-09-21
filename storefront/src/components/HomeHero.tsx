import Link from "next/link";
import { buttonClassName } from "@/components/ui/Button";
import { localePath } from "@/lib/i18n/paths";
import { previewSrc } from "@/lib/media";
import type { Dictionary, Locale } from "@/lib/i18n";
import type { CatalogueCard } from "@/lib/api";

type Props = {
  /** The first published good, used as the hero background. `null` when the catalogue is empty. */
  image: CatalogueCard | null;
  locale: Locale;
  dict: Dictionary;
};

/**
 * The generated print-room art, served as plain `<img>`: the files are already optimised WebP
 * and `next/image` would re-encode them. Both are decoration on a band whose copy carries the
 * meaning, so neither is given an accessible name.
 */
const PLATE_SRC = "/brand/generated/hero-printroom.webp";
const TEXTURE_SRC = "/brand/generated/paper-texture.webp";

/** The scrim a photograph needs: enough to keep light copy readable over an unknown image. */
const PHOTO_SCRIM =
  "absolute inset-0 bg-gradient-to-t from-surface-inverse/95 via-surface-inverse/70 to-surface-inverse/50";

/**
 * The heavier scrim the fallback plate needs. `hero-printroom.webp` is archival plates on a
 * paper ground, so it is light where a photograph is usually mid-tone, and the supporting line
 * is normal-sized text: at the identity's ratios a 70 percent wash over paper does not reach
 * the 4.5:1 it needs.
 */
const PLATE_SCRIM =
  "absolute inset-0 bg-gradient-to-t from-surface-inverse/95 via-surface-inverse/90 to-surface-inverse/75";

/**
 * The fibre texture, over the band and under the copy. The identity fixes its ceiling at four
 * percent, so it warms the band without ever competing with the text in front of it.
 */
const TEXTURE_CLASSES =
  "pointer-events-none absolute inset-0 h-full w-full object-cover opacity-[0.04]";

/**
 * The one value proposition and the one primary action.
 *
 * The background is a real catalogue image, not brand art: the point of the surface is that
 * these are specific goods, so the first thing a visitor sees is one of them. A dark overlay
 * keeps the copy readable whatever the image turns out to be, and it is decorative, so it is
 * hidden from assistive technology.
 *
 * With no goods there is no good to show, and the hero falls back to the identity's print-room
 * plate rather than to a bare colour: an empty catalogue is the first visit a brand-new shop
 * gets, so the fallback is the shop's face until the first good is published.
 */
export function HomeHero({ image, locale, dict }: Props) {
  return (
    <section
      aria-labelledby="home-hero-title"
      className="relative overflow-hidden bg-surface-inverse"
    >
      {image === null ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element -- the asset is already optimised WebP; next/image would re-encode it */}
          <img
            alt=""
            className="absolute inset-0 h-full w-full object-cover"
            src={PLATE_SRC}
            loading="eager"
            fetchPriority="high"
            decoding="async"
          />
          <div aria-hidden="true" className={PLATE_SCRIM} />
        </>
      ) : (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element -- the API serves an already optimised WebP; next/image would re-encode it */}
          <img
            className="absolute inset-0 h-full w-full object-cover"
            src={previewSrc(image.candidate_id)}
            alt={dict["home.heroImageAlt"]}
            loading="eager"
            fetchPriority="high"
            decoding="async"
          />
          <div aria-hidden="true" className={PHOTO_SCRIM} />
        </>
      )}
      {/* eslint-disable-next-line @next/next/no-img-element -- the asset is already optimised WebP; next/image would re-encode it */}
      <img
        alt=""
        className={TEXTURE_CLASSES}
        src={TEXTURE_SRC}
        loading="lazy"
        decoding="async"
      />
      <div className="relative mx-auto flex min-h-96 max-w-6xl flex-col items-start justify-center gap-5 px-gutter py-section-lg">
        <h1
          id="home-hero-title"
          className="max-w-3xl font-heading text-4xl font-semibold leading-tight text-ink-inverse sm:text-5xl"
        >
          {dict["home.heroTitle"]}
        </h1>
        <p className="max-w-prose text-lg text-ink-inverse/90">
          {dict["home.heroSupport"]}
        </p>
        <Link
          className={buttonClassName("primary", "lg")}
          href={localePath(locale, "/catalogue")}
        >
          {dict["home.heroCta"]}
        </Link>
      </div>
    </section>
  );
}
