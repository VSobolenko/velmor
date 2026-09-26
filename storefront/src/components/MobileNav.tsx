"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useCallback, useState } from "react";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Sheet } from "@/components/ui/Sheet";

export type NavLink = {
  href: string;
  label: string;
};

type Props = {
  links: readonly NavLink[];
  openLabel: string;
  closeLabel: string;
  title: string;
  searchAction: string;
  searchLabel: string;
  searchPlaceholder: string;
  languageSwitcher: ReactNode;
  /** The header's account control, shown in the drawer below `lg`. */
  account: ReactNode;
};

/**
 * The header below `lg`: one button, one drawer, the same links as the desktop row.
 *
 * The rows take the system's ghost-button class rather than repeating its hover, focus, radius
 * and target size here. The hand-written row had drifted to a different radius than every
 * other control, which is the kind of difference a buyer reads as a mistake without being able
 * to name it.
 */
export function MobileNav({
  links,
  openLabel,
  closeLabel,
  title,
  searchAction,
  searchLabel,
  searchPlaceholder,
  languageSwitcher,
  account,
}: Props) {
  const [open, setOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);

  return (
    <div className="flex shrink-0 items-center lg:hidden">
      <Button
        variant="secondary"
        size="sm"
        className="mr-2 w-11 px-0"
        aria-expanded={searchOpen}
        onClick={() => setSearchOpen((current) => !current)}
      >
        <span className="sr-only">{searchLabel}</span>
        <span
          aria-hidden="true"
          className="relative block h-4 w-4 rounded-full border-2 border-current after:absolute after:-bottom-1 after:-right-1 after:h-2 after:w-0.5 after:rotate-[-45deg] after:bg-current"
        />
      </Button>
      {searchOpen ? (
        <form
          className="absolute left-0 top-full w-full border-b border-line bg-surface p-4"
          role="search"
          action={searchAction}
          method="get"
        >
          <Input
            hideLabel
            label={searchLabel}
            name="q"
            type="search"
            placeholder={searchPlaceholder}
          />
        </form>
      ) : null}
      <Button
        variant="secondary"
        size="sm"
        className="w-11 px-0"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        <span className="sr-only">{openLabel}</span>
        <span aria-hidden="true" className="flex flex-col gap-1">
          <span className="block h-0.5 w-5 bg-current" />
          <span className="block h-0.5 w-5 bg-current" />
          <span className="block h-0.5 w-5 bg-current" />
        </span>
      </Button>
      <Sheet open={open} onClose={close} title={title} closeLabel={closeLabel}>
        <nav>
          <ul className="flex flex-col gap-1">
            {links.map((link) => (
              <li key={link.href}>
                <Link
                  className={buttonClassName("ghost", "md", "w-full")}
                  href={link.href}
                  onClick={close}
                >
                  <span className="w-full text-left">{link.label}</span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="mt-4">{account}</div>
        <div className="mt-4">{languageSwitcher}</div>
      </Sheet>
    </div>
  );
}
