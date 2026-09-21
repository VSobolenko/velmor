import Link from "next/link";
import { Wordmark } from "@/components/brand";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { CartLink } from "./CartLink";
import { LanguageSwitcher, type LocaleOption } from "./LanguageSwitcher";
import { MobileNav, type NavLink } from "./MobileNav";
import type { Dictionary, Locale } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";

type Props = {
  locale: Locale;
  dict: Dictionary;
};

/** The catalogue route the search field and the primary navigation submit to. */
const CATALOGUE_PATH = "/catalogue";

export function SiteHeader({ locale, dict }: Props) {
  const home = localePath(locale, "/");
  const catalogue = localePath(locale, CATALOGUE_PATH);
  const links: NavLink[] = [
    { href: home, label: dict["nav.home"] },
    { href: catalogue, label: dict["nav.catalogue"] },
    { href: localePath(locale, "/account"), label: dict["nav.account"] },
  ];
  const localeLabels: Record<Locale, string> = {
    ru: dict["common.localeRu"],
    be: dict["common.localeBe"],
    en: dict["common.localeEn"],
  };
  const localeOptions: LocaleOption[] = [
    { locale: "ru", label: localeLabels.ru },
    { locale: "be", label: localeLabels.be },
    { locale: "en", label: localeLabels.en },
  ];

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-surface/95 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-2 px-4 py-2">
        {/* The wordmark is the shop's own link home: it already renders the anchor and the
            accessible name, so wrapping it in another link would nest two links to one target. */}
        <Wordmark
          href={home}
          locale={locale}
          name={dict["common.brand"]}
          size="sm"
        />

        <nav aria-label={dict["nav.label"]} className="hidden md:block">
          <ul className="flex items-center gap-1">
            {links.map((link) => (
              <li key={link.href}>
                <Link
                  className={buttonClassName("ghost", "sm")}
                  href={link.href}
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <form
          className="order-last flex w-full items-end gap-2 md:order-none md:ml-auto md:w-auto"
          role="search"
          action={catalogue}
          method="get"
        >
          <Input
            hideLabel
            label={dict["common.searchLabel"]}
            name="q"
            type="search"
            placeholder={dict["common.searchPlaceholder"]}
            className="md:w-56"
          />
          <Button type="submit" variant="secondary">
            {dict["common.search"]}
          </Button>
        </form>

        <LanguageSwitcher
          locale={locale}
          label={dict["common.language"]}
          options={localeOptions}
        />

        <CartLink label={dict["nav.cart"]} countLabel={dict["cart.countLabel"]} />

        <MobileNav
          links={links}
          openLabel={dict["nav.openMenu"]}
          closeLabel={dict["nav.closeMenu"]}
          title={dict["nav.label"]}
        />
      </div>
    </header>
  );
}
