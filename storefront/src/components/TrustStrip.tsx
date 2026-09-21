import { HallmarkBadge } from "@/components/brand";
import type { Dictionary } from "@/lib/i18n";

const TRUST_KEYS: readonly (keyof Dictionary)[] = [
  "home.trustRights",
  "home.trustDownload",
  "home.trustLicence",
  "home.trustPayment",
];

/**
 * The one claim the hallmark belongs beside. The mark says a thing was verified, so it goes on
 * the statement about the check that was run and not on the delivery or payment conveniences
 * next to it.
 */
const RIGHTS_KEY = "home.trustRights";

type Props = {
  dict: Dictionary;
};

/**
 * The trust signal under the hero: rights first, then delivery, the licence and payment.
 *
 * The order is not cosmetic. The rights check is the reason this shop may sell the good at
 * all, so it is the first thing stated and the first step of "how it works".
 */
export function TrustStrip({ dict }: Props) {
  return (
    <section
      aria-labelledby="home-trust-title"
      className="border-y border-line bg-surface"
    >
      <div className="mx-auto max-w-6xl px-gutter py-section">
        <h2
          id="home-trust-title"
          className="font-heading text-2xl font-semibold text-ink"
        >
          {dict["home.trustTitle"]}
        </h2>
        <ul className="mt-6 grid gap-gutter sm:grid-cols-2 lg:grid-cols-4">
          {TRUST_KEYS.map((key) =>
            key === RIGHTS_KEY ? (
              <li key={key} className="flex items-start">
                <HallmarkBadge label={dict[key]} />
              </li>
            ) : (
              <li key={key} className="flex items-start gap-3">
                <svg
                  aria-hidden="true"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="mt-0.5 h-5 w-5 shrink-0 text-accent"
                >
                  <path d="M20 6L9 17l-5-5" />
                </svg>
                <span className="text-sm text-ink">{dict[key]}</span>
              </li>
            ),
          )}
        </ul>
      </div>
    </section>
  );
}
