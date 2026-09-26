"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { buttonClassName } from "@/components/ui/Button";
import { EmptyState, type StateHeadingLevel } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { signInHref } from "@/lib/i18n/paths";
import type { Locale } from "@/lib/i18n";

type SignInRequiredProps = {
  locale: Locale;
  title: string;
  actionLabel: string;
  /**
   * The panel's heading level in the page outline. The account gate's panel is the whole page
   * and takes level 1; the same prompt standing in for a section of a page that already has a
   * title takes level 2.
   */
  headingLevel?: StateHeadingLevel;
};

/**
 * What a visitor with no session sees where an account page or the checkout payment form would
 * be: a statement and one action, carrying the page they were on so signing in returns them
 * there. Client-side only because the current path is not available to a server component.
 */
export function SignInRequired({
  locale,
  title,
  actionLabel,
  headingLevel = 1,
}: SignInRequiredProps) {
  const pathname = usePathname();
  return (
    <EmptyState
      headingLevel={headingLevel}
      title={title}
      action={
        <Link
          className={buttonClassName("primary")}
          href={signInHref(locale, pathname)}
        >
          {actionLabel}
        </Link>
      }
    />
  );
}

type AccountUnavailableProps = {
  title: string;
  description: string;
  actionLabel: string;
};

/** The account service could not be reached: the same panel with a retry of the current path. */
export function AccountUnavailable({
  title,
  description,
  actionLabel,
}: AccountUnavailableProps) {
  const pathname = usePathname();
  return (
    <ErrorState
      headingLevel={1}
      title={title}
      description={description}
      action={
        <Link className={buttonClassName("secondary")} href={pathname}>
          {actionLabel}
        </Link>
      }
    />
  );
}
