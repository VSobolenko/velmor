import { HallmarkRule } from "@/components/brand";
import type { Dictionary } from "@/lib/i18n";

const QUESTIONS: readonly {
  question: keyof Dictionary;
  answer: keyof Dictionary;
}[] = [
  { question: "home.faqBuyQuestion", answer: "home.faqBuyAnswer" },
  { question: "home.faqUseQuestion", answer: "home.faqUseAnswer" },
  { question: "home.faqFileQuestion", answer: "home.faqFileAnswer" },
  { question: "home.faqRefundQuestion", answer: "home.faqRefundAnswer" },
];

type Props = {
  dict: Dictionary;
};

/**
 * The licence explainer: what is bought, what may be done with it, when the file arrives and
 * how refunds work.
 *
 * This is the plain-language counterpart of the disclosure a buyer must see before paying. It
 * is built on `details` / `summary`, so it opens and closes with no JavaScript and is keyboard
 * operable by default.
 *
 * It opens with the identity's rule, on the paper ground the rule is drawn for, so the section
 * is divided by the mark rather than by a hairline of its own.
 */
export function LicenceFaq({ dict }: Props) {
  return (
    <section
      aria-labelledby="home-faq-title"
      className="mx-auto max-w-6xl px-gutter pb-section-lg"
    >
      <HallmarkRule className="mb-8" />
      <h2
        id="home-faq-title"
        className="font-heading text-2xl font-semibold text-ink"
      >
        {dict["home.faqTitle"]}
      </h2>
      <div className="mt-6 flex flex-col gap-3">
        {QUESTIONS.map((item) => (
          <details
            key={item.question}
            className="rounded-lg border border-line bg-surface shadow-sm"
          >
            <summary className="tap-target flex cursor-pointer items-center justify-between gap-3 px-5 py-4 font-heading text-base font-semibold text-ink">
              {dict[item.question]}
            </summary>
            <p className="px-5 pb-5 text-sm text-muted">{dict[item.answer]}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
