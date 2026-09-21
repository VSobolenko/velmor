import type { Dictionary } from "@/lib/i18n";

type Props = {
  obligations: string[];
  dict: Dictionary;
};

/**
 * The licence obligations, each as its own item and each shown in full.
 *
 * This is not a comma list and it is not behind a disclosure widget: it is the disclosure of
 * what the buyer may do with the file, and the licence acknowledgement at checkout depends on
 * the buyer having seen it. `select-all` lets one click select the whole obligation, so an
 * attribution line can be copied out as it stands; that is the one affordance which needs
 * neither a new copy key nor a script.
 */
export function ObligationList({ obligations, dict }: Props) {
  if (obligations.length === 0) {
    return <p className="text-sm text-muted">{dict["product.noObligations"]}</p>;
  }

  return (
    <ul className="flex flex-col gap-2">
      {obligations.map((obligation) => (
        <li
          key={obligation}
          className="flex items-start gap-3 rounded-md border border-line bg-surface-muted p-3"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="mt-0.5 h-4 w-4 shrink-0 text-accent-strong"
          >
            <path d="M20 6L9 17l-5-5" />
          </svg>
          <span className="select-all text-base text-ink">{obligation}</span>
        </li>
      ))}
    </ul>
  );
}
