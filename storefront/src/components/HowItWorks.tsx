import { HallmarkRule } from "@/components/brand";
import { Card } from "@/components/ui/Card";
import type { Dictionary } from "@/lib/i18n";

const STEPS: readonly { title: keyof Dictionary; body: keyof Dictionary }[] = [
  { title: "home.howVerified", body: "home.howVerifiedBody" },
  { title: "home.howChoose", body: "home.howChooseBody" },
  { title: "home.howPay", body: "home.howPayBody" },
  { title: "home.howDownload", body: "home.howDownloadBody" },
];

type Props = {
  dict: Dictionary;
};

/**
 * The four steps, in order, as an ordered list so the sequence survives without CSS.
 *
 * The rights check is first deliberately: a good that cannot be justified is not listed, and
 * this page sells that ordering rather than hiding it.
 *
 * The section sits on the paper ground and is divided from the shop window above it by the
 * identity's rule rather than by a hairline border, which is what the identity uses a rule for.
 * The steps are raised plates, so they read against the paper the same way a good's card does.
 */
export function HowItWorks({ dict }: Props) {
  return (
    <section
      aria-labelledby="home-how-title"
      className="mx-auto max-w-6xl px-gutter py-section"
    >
      <HallmarkRule className="mb-8" />
      <h2
        id="home-how-title"
        className="font-heading text-2xl font-semibold text-ink"
      >
        {dict["home.howTitle"]}
      </h2>
      <ol className="mt-6 grid gap-gutter sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((step, index) => (
          <li key={step.title}>
            <Card className="flex h-full flex-col gap-2">
              <span
                aria-hidden="true"
                className="flex h-8 w-8 items-center justify-center rounded-pill bg-accent-soft font-heading text-sm font-semibold text-accent-strong"
              >
                {index + 1}
              </span>
              <h3 className="font-heading text-base font-semibold text-ink">
                {dict[step.title]}
              </h3>
              <p className="text-sm text-muted">{dict[step.body]}</p>
            </Card>
          </li>
        ))}
      </ol>
    </section>
  );
}
