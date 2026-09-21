import Link from "next/link";
import { HallmarkBadge } from "@/components/brand";
import { AddToCartButton } from "./AddToCartButton";
import { PreviewImage } from "./PreviewImage";
import { Badge } from "./ui/Badge";
import { Card } from "./ui/Card";
import { PriceTag } from "./ui/PriceTag";
import { formatFileSize, formatKeyFor } from "@/lib/format";
import { localePath } from "@/lib/i18n/paths";
import { previewSrc } from "@/lib/media";
import type { Dictionary, Locale } from "@/lib/i18n";
import type { CatalogueCard } from "@/lib/api/types";

type Props = {
  card: CatalogueCard;
  locale: Locale;
  dict: Dictionary;
};

/**
 * One good on a grid: a fixed 4:5 media box, the licence and the file kind on the image, the
 * title and size under it, and the price next to the action.
 *
 * The whole card is clickable through a stretched link on the title rather than by wrapping
 * the card in an anchor: the add-to-cart control has to stay a real button, and a button
 * inside a link is neither valid nor usable by keyboard. The action is always visible —
 * nothing here depends on hover.
 */
export function ProductCard({ card, locale, dict }: Props) {
  const href = localePath(
    locale,
    `/goods/${encodeURIComponent(card.candidate_id)}`,
  );
  const creator = card.creator ?? dict["product.unknownCreator"];

  return (
    <Card
      padding="none"
      className="group relative flex flex-col overflow-hidden transition-shadow duration-base ease-standard hover:shadow-md"
    >
      <div className="relative aspect-[4/5] overflow-hidden bg-surface-sunken">
        <PreviewImage
          className="transition-transform duration-base ease-standard group-hover:scale-[1.03]"
          src={previewSrc(card.candidate_id)}
          alt={card.title}
        />
        {/* The hallmark marks a verified thing, so it is stamped only on a good whose licence
            identity was recorded. A card with none states the absence in the neutral tone
            rather than wearing the mark that means the opposite. */}
        {card.license_id === null ? (
          <Badge className="absolute left-2 top-2">
            {dict["product.noLicence"]}
          </Badge>
        ) : (
          <HallmarkBadge
            className="absolute left-2 top-2"
            label={card.license_id}
          />
        )}
        <Badge className="absolute right-2 top-2">
          {dict[formatKeyFor(card.content_type)]}
        </Badge>
      </div>

      <div className="flex flex-1 flex-col gap-1 p-4">
        <h3 className="font-heading text-base font-semibold leading-snug text-ink">
          <Link className="after:absolute after:inset-0" href={href}>
            {card.title}
          </Link>
        </h3>
        <p className="text-sm text-muted">{creator}</p>
        <p className="text-sm text-muted">
          {formatFileSize(card.size_bytes, locale)}
        </p>
        <div className="mt-auto flex items-center justify-between gap-3 pt-3">
          <PriceTag amount={card.unit_amount} currency={card.currency} />
          <span className="relative z-10">
            <AddToCartButton
              candidateId={card.candidate_id}
              title={card.title}
              unitAmount={card.unit_amount}
              currency={card.currency}
              label={dict["product.addToCart"]}
              addedLabel={dict["product.addedToCart"]}
              size="sm"
            />
          </span>
        </div>
      </div>
    </Card>
  );
}
