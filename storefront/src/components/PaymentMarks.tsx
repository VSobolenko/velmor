import styles from "@/app/shop.module.css";
import { copy } from "@/lib/copy";

type Props = {
  marks: string[];
  labelled?: boolean;
};

/** Text badges for payment systems — no trademarked logo files. */
export function PaymentMarks({ marks, labelled = false }: Props) {
  if (marks.length === 0) {
    return null;
  }
  return (
    <div className={styles.paymentMarks}>
      {labelled ? (
        <p className={styles.paymentMarksLabel}>{copy.paymentMarks}</p>
      ) : null}
      <ul className={styles.paymentMarksList}>
        {marks.map((mark) => (
          <li key={mark} className={styles.paymentMark}>
            {mark}
          </li>
        ))}
      </ul>
    </div>
  );
}
