import { AddToCartButton } from "./AddToCartButton";
import { PreviewImage } from "./PreviewImage";
import { Badge } from "./ui/Badge";
import { PriceTag } from "./ui/PriceTag";
import { formatKeyFor } from "@/lib/format";
import { previewSrc } from "@/lib/media";
import type { Dictionary } from "@/lib/i18n";
import type { CatalogueCard } from "@/lib/api/types";

type Props = {
  card: CatalogueCard;
  dict: Dictionary;
};

/**
 * The id of the buy box's add-to-cart wrapper. `StickyBuyBar` observes it (with the repeat
 * below the detail) so the bar appears only while no in-flow action is on screen.
 */
export const BUY_BOX_ACTION_ID = "buy-box-action";

/**
 * The buy box: the decision, above the fold.
 *
 * At 390 px the media box is capped at 28vh so the image, the title, the price and the
 * add-to-cart all fit inside the first viewport, clear of the fixed mobile action bar; from
 * `md` the same markup becomes two columns, the image left and the offer right. That is the
 * pattern recorded in
 * `.cursor/skills/storefront-ux/SKILL.md` under "Keep the buy box - title, image, price, CTA,
 * one trust cue - inside the first mobile viewport".
 *
 * The image is `PreviewImage`, which renders a real placeholder when the bytes are absent: a
 * good with no usable preview must still not be a broken tile.
 */
export function BuyBox({ card, dict }: Props) {
  const creator = card.creator ?? dict["product.unknownCreator"];
  const licence = card.license_id ?? dict["product.noLicence"];

  return (
    <div className="grid gap-4 md:grid-cols-2 md:items-start md:gap-gutter-lg">
      <div className="relative aspect-[4/5] max-h-[28vh] w-full overflow-hidden rounded-lg border border-line bg-surface-sunken md:max-h-none">
        <PreviewImage src={previewSrc(card.candidate_id)} alt={card.title} />
        <Badge className="absolute left-2 top-2">
          {dict[formatKeyFor(card.content_type)]}
        </Badge>
      </div>

      <div className="flex flex-col gap-3">
        <h1 className="font-heading text-2xl font-semibold leading-tight text-ink md:text-3xl">
          {card.title}
        </h1>
        <p className="text-base text-muted">{creator}</p>

        <div className="flex flex-wrap items-center gap-3">
          <PriceTag
            amount={card.unit_amount}
            currency={card.currency}
            size="lg"
          />
          <Badge tone="accent">{licence}</Badge>
        </div>

        <div id={BUY_BOX_ACTION_ID}>
          <AddToCartButton
            candidateId={card.candidate_id}
            title={card.title}
            unitAmount={card.unit_amount}
            currency={card.currency}
            label={dict["product.addToCart"]}
            addedLabel={dict["product.addedToCart"]}
            size="lg"
            className="w-full md:w-auto"
          />
        </div>

        <p className="flex items-start gap-2 text-sm text-muted">
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="mt-0.5 h-4 w-4 shrink-0 text-accent-strong"
          >
            <path d="M20 6L9 17l-5-5" />
          </svg>
          {dict["product.trustCue"]}
        </p>

        <div className="flex flex-wrap items-baseline gap-x-2 text-sm">
          <span className="text-muted">{dict["product.originalTitle"]}</span>
          <span className="text-ink">{card.original_title}</span>
        </div>
      </div>
    </div>
  );
}
