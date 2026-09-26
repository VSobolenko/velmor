import type { ReactNode } from "react";
import {
  AccountUnavailable,
  SignInRequired,
} from "@/components/AccountGateActions";
import { readAccountState } from "@/lib/account";
import type { BuyerProfile } from "@/lib/api";
import { dictionaryFor, type Locale } from "@/lib/i18n";

export type AccountGateResult =
  | { allowed: true; profile: BuyerProfile }
  | { allowed: false; node: ReactNode };

/**
 * The session gate for every account page.
 *
 * `allowed: false` carries the surface a visitor without a session sees, and the page returns
 * it before reading anything, so an anonymous visitor never triggers an order, entitlement or
 * download read. `allowed: true` carries the buyer's own profile for the page that shows it.
 * The state is resolved once per request by `readAccountState`.
 */
export async function accountGate(locale: Locale): Promise<AccountGateResult> {
  const account = await readAccountState(locale);
  if (account.kind === "signedIn") {
    return { allowed: true, profile: account.profile };
  }
  const dict = dictionaryFor(locale);
  return {
    allowed: false,
    node: (
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-gutter px-gutter py-section">
        {account.kind === "anonymous" ? (
          <SignInRequired
            locale={locale}
            title={dict["account.signInRequired"]}
            actionLabel={dict["auth.signInAction"]}
          />
        ) : (
          <AccountUnavailable
            title={dict["common.errorTitle"]}
            description={dict["account.unavailable"]}
            actionLabel={dict["common.retry"]}
          />
        )}
      </main>
    ),
  };
}
