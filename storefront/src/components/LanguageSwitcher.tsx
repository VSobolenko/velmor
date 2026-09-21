"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { Select } from "@/components/ui/Select";
import { resolveLocale, type Locale } from "@/lib/i18n";
import { setLocaleCookie } from "@/lib/i18n/actions";
import { localePath } from "@/lib/i18n/paths";

export type LocaleOption = {
  locale: Locale;
  /** The language's own name: `Русский`, `Беларуская`, `English`. */
  label: string;
};

type Props = {
  locale: Locale;
  /** The accessible name of the control, in the active locale. */
  label: string;
  options: readonly LocaleOption[];
};

/**
 * Writes the preference cookie through a server action, then navigates to the same path under
 * the new prefix. The query string is read at change time: it is not part of the rendered
 * shell, and `useSearchParams` would put a Suspense boundary in front of every page.
 */
export function LanguageSwitcher({ locale, label, options }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const [pending, setPending] = useState(false);

  async function onChange(next: Locale): Promise<void> {
    if (next === locale || pending) {
      return;
    }
    const target = localePath(next, `${pathname}${window.location.search}`);
    setPending(true);
    // `finally` releases the control whether the action resolves or rejects; the rejection is
    // not caught, so a failed write still surfaces instead of disabling the switcher quietly.
    try {
      await setLocaleCookie(next);
      router.push(target);
    } finally {
      setPending(false);
    }
  }

  return (
    <Select
      label={label}
      hideLabel
      disabled={pending}
      value={locale}
      options={options.map((option) => ({
        value: option.locale,
        label: option.label,
      }))}
      onChange={(event) => {
        void onChange(resolveLocale(event.target.value));
      }}
    />
  );
}
