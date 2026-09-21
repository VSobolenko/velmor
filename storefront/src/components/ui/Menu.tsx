"use client";

/**
 * Wraps `@radix-ui/react-navigation-menu`. This file is the only place that Radix package
 * is imported; the header and the mobile drawer reach a menu through
 * `@/components/ui/Menu`.
 *
 * A navigation menu is not a list of links. Hand-rolling it is what loses roving tabindex
 * (arrows move between items, Tab leaves the menu), the focus restoration that puts focus
 * back on the trigger when a panel closes, the Escape handling on the open panel, and the
 * `aria-expanded` / `aria-controls` pair on the trigger. Radix owns those; this file owns
 * the token styling and the prop names.
 *
 * An entry with `items` renders a trigger with a panel and therefore carries
 * `aria-expanded`; a plain entry is a link and has no expanded state to carry.
 */

import * as NavigationMenu from "@radix-ui/react-navigation-menu";
import Link from "next/link";
import { classNames } from "./classes";

export type MenuOrientation = "horizontal" | "vertical";

export type MenuLink = {
  label: string;
  href: string;
};

export type MenuGroup = {
  label: string;
  items: readonly MenuLink[];
};

/** One entry in the bar: a link, or a trigger with a panel of links. */
export type MenuEntry = MenuLink | MenuGroup;

const LINK_CLASSES =
  "tap-target flex items-center rounded-md px-3 py-2 text-ink transition-colors duration-fast ease-standard hover:bg-surface-sunken";

const TRIGGER_CLASSES =
  "group tap-target inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-ink transition-colors duration-fast ease-standard hover:bg-surface-sunken";

type Props = {
  /** The accessible name of the navigation landmark, so a screen reader announces which
   * navigation this is when the header has more than one. */
  label: string;
  entries: readonly MenuEntry[];
  orientation?: MenuOrientation;
  /** Called after a link is followed, so a drawer holding this menu can close itself. */
  onNavigate?: () => void;
  className?: string;
};

function hasItems(entry: MenuEntry): entry is MenuGroup {
  return "items" in entry;
}

export function Menu({
  label,
  entries,
  orientation = "horizontal",
  onNavigate,
  className,
}: Props) {
  return (
    <NavigationMenu.Root
      aria-label={label}
      orientation={orientation}
      className={classNames("relative", className)}
    >
      <NavigationMenu.List
        className={classNames(
          "flex gap-1",
          orientation === "horizontal"
            ? "flex-row items-center"
            : "flex-col items-stretch",
        )}
      >
        {entries.map((entry) =>
          hasItems(entry) ? (
            <NavigationMenu.Item key={entry.label}>
              <NavigationMenu.Trigger className={TRIGGER_CLASSES}>
                {entry.label}
                <svg
                  aria-hidden="true"
                  viewBox="0 0 12 12"
                  className="h-3 w-3 stroke-current transition-transform duration-fast ease-standard group-data-[state=open]:rotate-180"
                >
                  <path
                    d="M2 4.5 6 8.5 10 4.5"
                    fill="none"
                    strokeWidth="1.5"
                  />
                </svg>
              </NavigationMenu.Trigger>
              <NavigationMenu.Content className="rounded-md border border-line bg-surface p-2 shadow-md">
                <ul className="flex flex-col gap-1">
                  {entry.items.map((item) => (
                    <li key={item.href}>
                      <NavigationMenu.Link
                        asChild
                        onSelect={() => onNavigate?.()}
                      >
                        <Link className={LINK_CLASSES} href={item.href}>
                          {item.label}
                        </Link>
                      </NavigationMenu.Link>
                    </li>
                  ))}
                </ul>
              </NavigationMenu.Content>
            </NavigationMenu.Item>
          ) : (
            <NavigationMenu.Item key={entry.href}>
              <NavigationMenu.Link asChild onSelect={() => onNavigate?.()}>
                <Link className={LINK_CLASSES} href={entry.href}>
                  {entry.label}
                </Link>
              </NavigationMenu.Link>
            </NavigationMenu.Item>
          ),
        )}
      </NavigationMenu.List>
      <NavigationMenu.Viewport
        className={classNames(
          "w-full",
          orientation === "horizontal"
            ? "absolute left-0 top-full"
            : "static",
        )}
      />
    </NavigationMenu.Root>
  );
}
