"use client";

import { useState } from "react";
import { classNames } from "@/components/ui/classes";

type Props = {
  /** A `/media/preview/...` path: the storefront's proxy, never the API host. */
  src: string;
  /** The good's title. This is an image of one specific good, not decoration. */
  alt: string;
  className?: string;
};

/**
 * The identity's plate for a good with no preview: a framed empty plate in the paper and ink
 * tones, so the absent bytes degrade to a designed placeholder rather than to a broken tile.
 * It is served as plain `<img>` because the file is already optimised WebP and `next/image`
 * would re-encode it.
 */
const PLACEHOLDER_SRC = "/brand/generated/plate-placeholder.webp";

/** The plate's own 4:5 proportion, declared so the media box is reserved before it loads. */
const PLACEHOLDER_WIDTH = 800;
const PLACEHOLDER_HEIGHT = 1000;

/**
 * A good's preview, with a real placeholder when the bytes are absent.
 *
 * A plain `<img>` rather than `next/image`: the API already serves an optimised, bounded
 * WebP and re-encoding it here would cost quality and a round trip (contract.md, "Storefront
 * media route").
 *
 * A failed image becomes the identity's plate rather than a broken tile. For a visual good, a
 * card with no image is the failure this surface was rebuilt to remove, so it must never be an
 * empty box or a line of text.
 *
 * The plate is a frame and says nothing about which good is underneath it, so it stays
 * decorative (`alt=""`) and the wrapper keeps the `role="img"` and the good's title: the
 * picture is the visual, the accessible name is the information, and a buyer who cannot see
 * the card still learns which good it is.
 */
export function PreviewImage({ src, alt, className }: Props) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div
        role="img"
        aria-label={alt}
        className={classNames("h-full w-full bg-surface-sunken", className)}
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- the asset is already optimised WebP; next/image would re-encode it */}
        <img
          alt=""
          className="h-full w-full object-cover"
          decoding="async"
          height={PLACEHOLDER_HEIGHT}
          loading="lazy"
          src={PLACEHOLDER_SRC}
          width={PLACEHOLDER_WIDTH}
        />
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element -- the API serves an already optimised WebP; next/image would re-encode it
    <img
      className={classNames("h-full w-full object-cover", className)}
      src={src}
      alt={alt}
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
    />
  );
}
