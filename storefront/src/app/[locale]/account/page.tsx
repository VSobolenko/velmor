import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { dictionaryFor, resolveLocale } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";

type Props = {
  params: Promise<{ locale: string }>;
};

export default async function AccountPage({ params }: Props) {
  const { locale: rawLocale } = await params;
  const locale = resolveLocale(rawLocale);
  const dict = dictionaryFor(locale);
  const entries = [
    {
      href: localePath(locale, "/account/orders"),
      title: dict["account.orders"],
      hint: dict["account.ordersHint"],
    },
    {
      href: localePath(locale, "/account/entitlements"),
      title: dict["account.entitlements"],
      hint: dict["account.entitlementsHint"],
    },
  ];

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-gutter px-gutter py-section">
      <h1 className="font-heading text-2xl font-semibold text-ink">
        {dict["account.title"]}
      </h1>
      <p className="max-w-prose text-sm text-muted">
        {dict["account.demoNote"]}
      </p>
      <ul className="grid gap-gutter sm:grid-cols-2">
        {entries.map((entry) => (
          <li key={entry.href}>
            <Card variant="flat" className="flex h-full flex-col gap-1">
              <h2 className="font-heading text-lg font-semibold text-ink">
                <Link className="hover:underline" href={entry.href}>
                  {entry.title}
                </Link>
              </h2>
              <p className="text-sm text-muted">{entry.hint}</p>
            </Card>
          </li>
        ))}
      </ul>
    </main>
  );
}
