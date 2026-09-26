"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Button, buttonClassName } from "@/components/ui/Button";
import { CommerceApiClient, type BuyerProfile } from "@/lib/api";
import { signInHref } from "@/lib/i18n/paths";
import { useLocale } from "@/lib/i18n/use-locale";

type Props = {
  profile: BuyerProfile | null;
  signInLabel: string;
  signOutLabel: string;
  signingOutLabel: string;
};

/**
 * The header's account control. With no session it is the one action to sign in; with a session
 * it shows the buyer's own display name and an action to sign out. Client-side because it reads
 * the current path and performs the sign-out request.
 */
export function HeaderAccount({
  profile,
  signInLabel,
  signOutLabel,
  signingOutLabel,
}: Props) {
  const locale = useLocale();
  const pathname = usePathname();
  const [busy, setBusy] = useState(false);

  if (profile === null) {
    return (
      <Link
        className={buttonClassName("secondary", "sm")}
        href={signInHref(locale, pathname)}
      >
        {signInLabel}
      </Link>
    );
  }

  async function signOut(): Promise<void> {
    setBusy(true);
    await CommerceApiClient.fromEnv(locale).signOut();
    // A full navigation is what makes the server render the signed-out header; the cookie is
    // gone and nothing client-side holds the profile.
    window.location.assign(pathname);
  }

  return (
    <div className="flex min-w-0 items-center gap-2">
      <span className="hidden max-w-40 truncate text-sm text-muted sm:inline">
        {profile.display_name}
      </span>
      <Button
        variant="ghost"
        size="sm"
        loading={busy}
        loadingLabel={signingOutLabel}
        onClick={() => {
          void signOut();
        }}
      >
        {signOutLabel}
      </Button>
    </div>
  );
}
