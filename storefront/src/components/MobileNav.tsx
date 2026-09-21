"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { Button, buttonClassName } from "@/components/ui/Button";
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
};

/**
 * The header below `md`: one button, one drawer, the same links as the desktop row.
 *
 * The rows take the system's ghost-button class rather than repeating its hover, focus, radius
 * and target size here. The hand-written row had drifted to a different radius than every
 * other control, which is the kind of difference a buyer reads as a mistake without being able
 * to name it.
 */
export function MobileNav({ links, openLabel, closeLabel, title }: Props) {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);

  return (
    <div className="md:hidden">
      <Button
        variant="secondary"
        size="sm"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        {openLabel}
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
      </Sheet>
    </div>
  );
}
