import Link from "next/link";
import styles from "./shop.module.css";

export default function NotFound() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <p className={styles.brand}>
          <Link href="/">Proofbasket</Link>
        </p>
        <p className={styles.tagline}>Not found</p>
      </header>
      <main className={styles.main}>
        <h1 className={styles.heading}>Not found</h1>
        <p className={styles.empty}>
          That category or good is not in the catalogue.
        </p>
        <p className={styles.actions}>
          <Link className={styles.linkButton} href="/">
            Back to shop
          </Link>
        </p>
      </main>
    </div>
  );
}
