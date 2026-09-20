import Link from "next/link";
import { ShopChrome } from "@/components/ShopChrome";
import styles from "./shop.module.css";

export default function NotFound() {
  return (
    <div className={styles.page}>
      <ShopChrome tagline="Not found" />
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
