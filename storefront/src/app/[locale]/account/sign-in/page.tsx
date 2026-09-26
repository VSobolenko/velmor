"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";
import {
  CommerceApiClient,
  CommerceApiError,
  type CommerceApiReason,
} from "@/lib/api";
import { dictionaryFor, type Dictionary } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";
import { useLocale } from "@/lib/i18n/use-locale";

/**
 * The reasons a sign-in can be refused, mapped to the key that says so in the buyer's language.
 * `detail` is never shown: it is the API's sentence for logs, not copy.
 */
const REFUSAL_KEYS: Partial<Record<CommerceApiReason, keyof Dictionary>> = {
  email_required: "auth.emailRequired",
  invalid_credentials: "auth.mismatch",
  rate_limited: "auth.rateLimited",
};

/**
 * The path to return to after signing in: the `next` query value when it is a site-relative
 * path, and the account landing page otherwise. A value like `//host` or an absolute URL is
 * rejected so the form cannot be turned into an open redirect.
 */
function returnPath(fallback: string): string {
  const value = new URLSearchParams(window.location.search).get("next");
  if (value === null || value === "") {
    return fallback;
  }
  if (!value.startsWith("/") || value.startsWith("//")) {
    return fallback;
  }
  return value;
}

type Refusal = {
  key: keyof Dictionary;
  minimumLength: number | null;
};

export default function SignInPage() {
  const locale = useLocale();
  const dict = dictionaryFor(locale);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setRefusal(null);
    setUnavailable(false);
    try {
      await CommerceApiClient.fromEnv(locale).signIn({ email, password });
      window.location.assign(returnPath(localePath(locale, "/account")));
    } catch (error) {
      // A refusal is a value the API documents with a stable code, and it becomes the sentence
      // in the buyer's language. Anything else - a fault, a transport failure - is presented as
      // an unavailable service with a way to try again.
      const key =
        error instanceof CommerceApiError && error.reason !== "fault"
          ? REFUSAL_KEYS[error.reason] ?? "auth.refused"
          : null;
      if (key === null) {
        setUnavailable(true);
      } else {
        setRefusal({
          key,
          minimumLength:
            error instanceof CommerceApiError ? error.minimumLength : null,
        });
      }
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-gutter px-gutter py-section">
      <h1 className="font-heading text-2xl font-semibold text-ink">
        {dict["auth.signInTitle"]}
      </h1>

      {unavailable ? (
        <ErrorState
          title={dict["auth.serviceUnavailable"]}
          description={dict["common.errorBody"]}
          action={
            <Button
              variant="secondary"
              size="md"
              onClick={() => setUnavailable(false)}
            >
              {dict["common.retry"]}
            </Button>
          }
        />
      ) : (
        <Card>
          <form
            className="flex flex-col gap-4"
            noValidate
            onSubmit={(event) => {
              void onSubmit(event);
            }}
          >
            <Input
              label={dict["auth.emailLabel"]}
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <Input
              label={dict["auth.passwordLabel"]}
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            {refusal === null ? null : (
              <div
                role="alert"
                className="flex flex-col gap-1 text-sm text-danger"
              >
                <p>{dict[refusal.key]}</p>
                {refusal.minimumLength === null ? null : (
                  <p>{`${dict["auth.minimumLength"]}: ${refusal.minimumLength}`}</p>
                )}
              </div>
            )}
            <Button
              type="submit"
              loading={busy}
              loadingLabel={dict["auth.signingIn"]}
            >
              {dict["auth.signInAction"]}
            </Button>
          </form>
        </Card>
      )}

      <Link
        className="tap-target inline-flex w-fit items-center text-sm font-medium text-accent-strong hover:underline"
        href={localePath(locale, "/account/sign-up")}
      >
        {dict["auth.toSignUp"]}
      </Link>
    </main>
  );
}
