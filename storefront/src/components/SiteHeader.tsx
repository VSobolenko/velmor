import Link from "next/link";
import { Wordmark } from "@/components/brand";
import { HeaderAccount } from "@/components/HeaderAccount";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { CartLink } from "./CartLink";
import { LanguageSwitcher, type LocaleOption } from "./LanguageSwitcher";
import { MobileNav, type NavLink } from "./MobileNav";
import type { BuyerProfile } from "@/lib/api";
import type { Dictionary, Locale } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";

type Props = {
  locale: Locale;
  dict: Dictionary;
  /** The signed-in buyer, or `null` for a visitor with no session. */
  profile: BuyerProfile | null;
};

/** The catalogue route the search field and the primary navigation submit to. */
const CATALOGUE_PATH = "/catalogue";

export function SiteHeader({ locale, dict, profile }: Props) {
  const home = localePath(locale, "/");
  const catalogue = localePath(locale, CATALOGUE_PATH);
  const links: NavLink[] = [
    { href: home, label: dict["nav.home"] },
    { href: catalogue, label: dict["nav.catalogue"] },
    // The account is offered only to a buyer who has one; a visitor is offered sign-in instead,
    // through the account control below.
    ...(profile === null
      ? []
      : [{ href: localePath(locale, "/account"), label: dict["nav.account"] }]),
  ];
  const account = (
    <HeaderAccount
      profile={profile}
      signInLabel={dict["nav.signIn"]}
      signOutLabel={dict["nav.signOut"]}
      signingOutLabel={dict["nav.signingOut"]}
    />
  );
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
      <div className="relative mx-auto flex h-16 w-full max-w-6xl flex-nowrap items-center gap-2 px-4">
        {/* The wordmark is the shop's own link home: it already renders the anchor and the
            accessible name, so wrapping it in another link would nest two links to one target. */}
        <Wordmark
          href={home}
          locale={locale}
          name={dict["common.brand"]}
          size="sm"
        />

        <nav aria-label={dict["nav.label"]} className="hidden lg:block">
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
          className="ml-auto hidden items-end gap-2 lg:flex"
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
            className="lg:w-56"
          />
          <Button type="submit" variant="secondary">
            {dict["common.search"]}
          </Button>
        </form>

        <div className="hidden lg:block">
          <LanguageSwitcher
            compact
            locale={locale}
            label={dict["common.language"]}
            options={localeOptions}
          />
        </div>

        <div className="hidden lg:block">{account}</div>

        <div className="ml-auto lg:ml-0">
          <CartLink label={dict["nav.cart"]} countLabel={dict["cart.countLabel"]} />
        </div>

        <MobileNav
          links={links}
          openLabel={dict["nav.openMenu"]}
          closeLabel={dict["nav.closeMenu"]}
          title={dict["nav.label"]}
          searchAction={catalogue}
          searchLabel={dict["common.searchLabel"]}
          searchPlaceholder={dict["common.searchPlaceholder"]}
          languageSwitcher={
            <LanguageSwitcher
              locale={locale}
              label={dict["common.language"]}
              options={localeOptions}
            />
          }
          account={account}
        />
      </div>
    </header>
  );
}
