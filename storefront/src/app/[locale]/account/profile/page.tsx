import Link from "next/link";
import { accountGate } from "@/components/AccountGate";
import { Card } from "@/components/ui/Card";
import { dictionaryFor, resolveLocale } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";

type Props = {
  params: Promise<{ locale: string }>;
};

export default async function ProfilePage({ params }: Props) {
  const { locale: rawLocale } = await params;
  const locale = resolveLocale(rawLocale);
  const dict = dictionaryFor(locale);
  const gate = await accountGate(locale);
  if (!gate.allowed) {
    return gate.node;
  }
  const profile = gate.profile;

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-gutter px-gutter py-section">
      <h1 className="font-heading text-2xl font-semibold text-ink">
        {dict["account.profile"]}
      </h1>
      <Link
        className="tap-target inline-flex w-fit items-center text-sm text-muted hover:underline"
        href={localePath(locale, "/account")}
      >
        {dict["account.backToAccount"]}
      </Link>

      <Card>
        <dl className="flex flex-col gap-3">
          <div className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
            <dt className="text-sm text-muted sm:w-56 sm:shrink-0">
              {dict["auth.displayNameLabel"]}
            </dt>
            <dd className="break-words text-base text-ink">
              {profile.display_name}
            </dd>
          </div>
          <div className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
            <dt className="text-sm text-muted sm:w-56 sm:shrink-0">
              {dict["auth.emailLabel"]}
            </dt>
            <dd className="break-words text-base text-ink">{profile.email}</dd>
          </div>
        </dl>
      </Card>

      <Link
        className="tap-target inline-flex w-fit items-center text-sm font-medium text-accent-strong hover:underline"
        href={localePath(locale, "/account/password")}
      >
        {dict["account.changePassword"]}
      </Link>
    </main>
  );
}
