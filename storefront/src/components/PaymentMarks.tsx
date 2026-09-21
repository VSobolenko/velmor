type Props = {
  /** The mark strings the API reports; rendered as text, there are no logo files. */
  marks: string[];
  /** The buyer-facing label above the marks, from the active locale's dictionary. */
  label: string;
};

/** Text badges for payment systems. The label and the marks are both supplied by the caller. */
export function PaymentMarks({ marks, label }: Props) {
  if (marks.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-medium text-ink">{label}</p>
      <ul className="flex flex-wrap gap-2">
        {marks.map((mark) => (
          <li
            key={mark}
            className="rounded-pill border border-line-strong bg-surface px-3 py-1 text-sm text-ink"
          >
            {mark}
          </li>
        ))}
      </ul>
    </div>
  );
}
