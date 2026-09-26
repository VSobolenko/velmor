"use client";

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
import { useLocale } from "@/lib/i18n/use-locale";

/**
 * The reasons a password change can be refused, mapped to the key that says so in the buyer's
 * language. The minimum length is never written into the dictionary; it is shown from the value
 * the API owns when a refusal carries it.
 */
const REFUSAL_KEYS: Partial<Record<CommerceApiReason, keyof Dictionary>> = {
  current_password_incorrect: "account.wrongPassword",
  password_too_short: "auth.passwordRule",
};

type Refusal = {
  key: keyof Dictionary;
  minimumLength: number | null;
};

export function ChangePasswordForm() {
  const locale = useLocale();
  const dict = dictionaryFor(locale);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [changed, setChanged] = useState(false);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setChanged(false);
    setRefusal(null);
    setUnavailable(false);
    try {
      await CommerceApiClient.fromEnv(locale).changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      // The passwords that were typed are dropped from the form on success.
      setCurrentPassword("");
      setNewPassword("");
      setChanged(true);
    } catch (error) {
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
    }
    setBusy(false);
  }

  if (unavailable) {
    return (
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
    );
  }

  return (
    <Card>
      <form
        className="flex flex-col gap-4"
        noValidate
        onSubmit={(event) => {
          void onSubmit(event);
        }}
      >
        <Input
          label={dict["account.currentPassword"]}
          name="current_password"
          type="password"
          autoComplete="current-password"
          value={currentPassword}
          onChange={(event) => setCurrentPassword(event.target.value)}
        />
        <Input
          label={dict["account.newPassword"]}
          name="new_password"
          type="password"
          autoComplete="new-password"
          value={newPassword}
          onChange={(event) => setNewPassword(event.target.value)}
        />
        <p className="text-sm text-muted">{dict["auth.passwordRule"]}</p>
        {refusal === null ? null : (
          <div role="alert" className="flex flex-col gap-1 text-sm text-danger">
            <p>{dict[refusal.key]}</p>
            {refusal.minimumLength === null ? null : (
              <p>{`${dict["auth.minimumLength"]}: ${refusal.minimumLength}`}</p>
            )}
          </div>
        )}
        {changed ? (
          <p role="status" className="text-sm text-ink">
            {dict["account.passwordChanged"]}
          </p>
        ) : null}
        <Button
          type="submit"
          loading={busy}
          loadingLabel={dict["account.changingPassword"]}
        >
          {dict["account.changePassword"]}
        </Button>
      </form>
    </Card>
  );
}
