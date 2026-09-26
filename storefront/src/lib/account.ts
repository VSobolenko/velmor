import { cache } from "react";
import { CommerceApiError, type BuyerProfile } from "@/lib/api";
import { commerceApiForServer } from "@/lib/api/server";
import type { Locale } from "@/lib/i18n";

/**
 * What the header and the account gate need to know about the caller.
 *
 * `signedIn` carries the buyer's profile, `anonymous` means the API answered `401`, and
 * `unavailable` means the account service could not be reached. The header offers the sign-in
 * action in both of the latter, and the account gate tells them apart: anonymous is asked to
 * sign in, unavailable is told to try again.
 */
export type AccountState =
  | { kind: "signedIn"; profile: BuyerProfile }
  | { kind: "anonymous" }
  | { kind: "unavailable" };

/**
 * The signed-in buyer or the reason there is none, resolved once per request.
 *
 * `cache` keeps the header and the account layout from each issuing their own `/auth/me` read
 * within one render. A `401` is the API's `unauthenticated` answer and means anonymous; any
 * other API error means the service could not be reached. A fault thrown in this process, such
 * as a missing build variable, is rethrown to the `error.tsx` boundary, as the account pages
 * already do.
 */
export const readAccountState = cache(
  async (locale: Locale): Promise<AccountState> => {
    try {
      const profile = await (await commerceApiForServer(locale)).getProfile();
      return { kind: "signedIn", profile };
    } catch (error) {
      if (!(error instanceof CommerceApiError)) {
        throw error;
      }
      return error.status === 401 ? { kind: "anonymous" } : { kind: "unavailable" };
    }
  },
);
