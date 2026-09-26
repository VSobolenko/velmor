import { CheckoutForm } from "@/components/CheckoutForm";
import { readAccountState } from "@/lib/account";
import { resolveLocale } from "@/lib/i18n";

type Props = {
  params: Promise<{ locale: string }>;
};

/**
 * Checkout needs an identifiable buyer, so the session is resolved here rather than in the
 * browser: the payment controls are not rendered at all for a visitor with no session, and the
 * cart, the seller disclosure and the way back to the cart stay readable for them.
 *
 * `readAccountState` is the same cached `/auth/me` read the header makes, so the page costs no
 * extra request and the header and the payment form cannot disagree about the session. An
 * account service that cannot be reached is reported as no session, exactly as the header
 * reports it, and the cart in `localStorage` survives the sign-in round trip unchanged.
 */
export default async function CheckoutPage({ params }: Props) {
  const { locale: rawLocale } = await params;
  const locale = resolveLocale(rawLocale);
  const account = await readAccountState(locale);
  return <CheckoutForm signedIn={account.kind === "signedIn"} />;
}
