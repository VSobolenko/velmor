import Link from "next/link";
import { accountGate } from "@/components/AccountGate";
import { ChangePasswordForm } from "@/components/ChangePasswordForm";
import { dictionaryFor, resolveLocale } from "@/lib/i18n";
import { localePath } from "@/lib/i18n/paths";

type Props = {
  params: Promise<{ locale: string }>;
};

export default async function PasswordPage({ params }: Props) {
  const { locale: rawLocale } = await params;
  const locale = resolveLocale(rawLocale);
  const dict = dictionaryFor(locale);
  const gate = await accountGate(locale);
  if (!gate.allowed) {
    return gate.node;
  }

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-gutter px-gutter py-section">
      <h1 className="font-heading text-2xl font-semibold text-ink">
        {dict["account.changePassword"]}
      </h1>
      <Link
        className="tap-target inline-flex w-fit items-center text-sm text-muted hover:underline"
        href={localePath(locale, "/account")}
      >
        {dict["account.backToAccount"]}
      </Link>
      <ChangePasswordForm />
    </main>
  );
}
