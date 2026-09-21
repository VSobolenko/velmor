import Link from "next/link";
import { notFound } from "next/navigation";
import { AddToCartButton } from "@/components/AddToCartButton";
import { BUY_BOX_ACTION_ID, BuyBox } from "@/components/BuyBox";
import { ObligationList } from "@/components/ObligationList";
import { RelatedGoods } from "@/components/RelatedGoods";
import { StickyBuyBar } from "@/components/StickyBuyBar";
import { buttonClassName } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import {
  CommerceApiClient,
  CommerceApiError,
  type CatalogueCard,
} from "@/lib/api";
import { formatFileSize, formatKeyFor } from "@/lib/format";
import { dictionaryFor, resolveLocale } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";

export const dynamic = "force-dynamic";

/** Related goods fill the grid's last row; the good being viewed is dropped from it. */
const RELATED_LIMIT = 5;

/** The in-flow action repeated below the detail; the sticky bar mirrors it as well. */
const DETAIL_ACTION_ID = "detail-action";

type Props = {
  params: Promise<{ locale: string; candidateId: string }>;
};

type GoodPageData =
  | { kind: "ok"; card: CatalogueCard; related: CatalogueCard[] }
  | { kind: "missing" }
  | { kind: "error" };

/**
 * A withdrawn or unpublished good is a 404 by contract, and `notFound()` renders the shared
 * `not-found.tsx` surface. Any other API failure is a state the buyer sees in the active
 * locale, with a retry. A fault thrown in this process instead, such as a missing build
 * variable, is not an API failure and is rethrown to the `error.tsx` boundary.
 */
async function loadGoodPage(
  client: CommerceApiClient,
  candidateId: string,
): Promise<GoodPageData> {
  try {
    const card = await client.getGood(candidateId);
    if (card.category_slug === null) {
      return { kind: "ok", card, related: [] };
    }
    const page = await client.listGoods({
      category: card.category_slug,
      limit: RELATED_LIMIT,
    });
    const related = page.items.filter(
      (item) => item.candidate_id !== card.candidate_id,
    );
    return { kind: "ok", card, related };
  } catch (error) {
    if (error instanceof CommerceApiError && error.status === 404) {
      return { kind: "missing" };
    }
    if (!(error instanceof CommerceApiError)) {
      throw error;
    }
    return { kind: "error" };
  }
}

export default async function GoodPage({ params }: Props) {
  const { locale: rawLocale, candidateId } = await params;
  const locale = resolveLocale(rawLocale);
  const dict = dictionaryFor(locale);
  const client = CommerceApiClient.fromEnv(locale);
  const data = await loadGoodPage(client, candidateId);

  if (data.kind === "missing") {
    notFound();
  }

  if (data.kind === "error") {
    return (
      <main className="mx-auto w-full max-w-6xl px-gutter py-section">
        <ErrorState
          headingLevel={1}
          title={dict["common.errorTitle"]}
          description={dict["common.errorBody"]}
          action={
            <Link
              className={buttonClassName("secondary")}
              href={localePath(locale, `/goods/${candidateId}`)}
            >
              {dict["common.retry"]}
            </Link>
          }
        />
      </main>
    );
  }

  const { card, related } = data;

  return (
    <div className="relative">
      <main className="mx-auto w-full max-w-6xl px-gutter py-6 md:py-section">
        <Link
          className={buttonClassName("ghost", "sm")}
          href={localePath(locale, "/catalogue")}
        >
          {dict["product.backToCatalogue"]}
        </Link>

        <div className="mt-3">
          <BuyBox card={card} dict={dict} />
        </div>

        {card.summary === null ? null : (
          <section className="mt-10">
            <h2 className="font-heading text-xl font-semibold text-ink">
              {dict["product.summary"]}
            </h2>
            <p className="mt-3 max-w-prose text-base text-ink">
              {card.summary}
            </p>
          </section>
        )}

        <section className="mt-10">
          <h2 className="font-heading text-xl font-semibold text-ink">
            {dict["product.obligations"]}
          </h2>
          <div className="mt-3 max-w-3xl">
            <ObligationList obligations={card.obligations} dict={dict} />
          </div>
        </section>

        <section className="mt-10">
          <h2 className="font-heading text-xl font-semibold text-ink">
            {dict["product.details"]}
          </h2>
          <dl className="mt-3 grid max-w-3xl gap-x-6 gap-y-4 sm:grid-cols-2">
            <div>
              <dt className="text-sm text-muted">{dict["product.fileType"]}</dt>
              <dd className="text-base text-ink">
                {dict[formatKeyFor(card.content_type)]}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-muted">{dict["product.fileSize"]}</dt>
              <dd className="text-base text-ink">
                {card.size_bytes === null
                  ? dict["product.sizeUnknown"]
                  : formatFileSize(card.size_bytes, locale)}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-muted">{dict["product.licence"]}</dt>
              <dd className="text-base text-ink">
                {card.license_id ?? dict["product.noLicence"]}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-muted">{dict["product.delivery"]}</dt>
              <dd className="text-base text-ink">
                {dict["product.deliveryBody"]}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-muted">{dict["product.refund"]}</dt>
              <dd className="text-base text-ink">
                {dict["product.refundBody"]}
              </dd>
            </div>
          </dl>
          {card.preview_is_cover ? (
            <p className="mt-4 text-sm text-muted">
              {dict["product.generatedCover"]}
            </p>
          ) : null}
        </section>

        <div id={DETAIL_ACTION_ID} className="mt-10">
          <AddToCartButton
            candidateId={card.candidate_id}
            title={card.title}
            unitAmount={card.unit_amount}
            currency={card.currency}
            label={dict["product.addToCart"]}
            addedLabel={dict["product.addedToCart"]}
            size="lg"
          />
        </div>

        <div className="mt-14">
          <RelatedGoods cards={related} locale={locale} dict={dict} />
        </div>
      </main>

      <StickyBuyBar
        candidateId={card.candidate_id}
        title={card.title}
        unitAmount={card.unit_amount}
        currency={card.currency}
        dict={dict}
        anchorIds={[BUY_BOX_ACTION_ID, DETAIL_ACTION_ID]}
      />
    </div>
  );
}
