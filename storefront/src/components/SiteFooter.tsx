import Link from "next/link";
import { HallmarkRule, Wordmark } from "@/components/brand";
import type { Dictionary, Locale } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";

type Props = {
  locale: Locale;
  dict: Dictionary;
};

export function SiteFooter({ locale, dict }: Props) {
  const links = [
    { href: localePath(locale, "/"), label: dict["nav.home"] },
    { href: localePath(locale, "/catalogue"), label: dict["nav.catalogue"] },
    { href: localePath(locale, "/account"), label: dict["nav.account"] },
    {
      href: localePath(locale, "/checkout#disclosure"),
      label: dict["footer.disclosure"],
    },
  ];
  const marks = [
    dict["footer.markStripe"],
    dict["footer.markBepaid"],
    dict["footer.markErip"],
  ];

  return (
    <footer className="bg-paper">
      {/*
       * The identity's closing device: the hallmark rule divides the page from the footer,
       * where the footer previously had a bare hairline. It is drawn on the paper ground the
       * rule is built for. The inverse band below cannot carry it - the mark sits in a
       * `bg-paper` box, which would show as a rectangle on the dark surface.
       */}
      <div className="mx-auto w-full max-w-6xl px-4 pt-section pb-8">
        <HallmarkRule />
      </div>

      <div className="bg-surface-inverse text-ink-inverse">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-10">
          <div className="flex flex-col gap-1">
            <Wordmark
              href={localePath(locale, "/")}
              locale={locale}
              name={dict["footer.brand"]}
              size="md"
            />
            <p className="text-sm text-ink-inverse/80">{dict["footer.tagline"]}</p>
          </div>

          <p className="max-w-prose text-sm text-ink-inverse/80">
            {dict["footer.rightsNote"]}
          </p>

          <nav aria-label={dict["footer.navTitle"]}>
            <h2 className="text-sm font-semibold">{dict["footer.navTitle"]}</h2>
            <ul className="mt-2 flex flex-col gap-1">
              {links.map((link) => (
                <li key={link.href}>
                  <Link
                    className="tap-target inline-flex items-center text-sm hover:underline"
                    href={link.href}
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div>
            <h2 className="text-sm font-semibold">{dict["footer.paymentMarks"]}</h2>
            <ul className="mt-2 flex flex-wrap gap-2">
              {marks.map((mark) => (
                <li
                  className="rounded-pill border border-ink-inverse/30 px-3 py-1 text-sm"
                  key={mark}
                >
                  {mark}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </footer>
  );
}
