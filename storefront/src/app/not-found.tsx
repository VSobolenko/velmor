import Link from "next/link";
import { ShopChrome } from "@/components/ShopChrome";
import { copy } from "@/lib/copy";
import styles from "./shop.module.css";

export default function NotFound() {
  return (
    <ShopChrome tagline={copy.notFound}>
      <main className={styles.main}>
        <h1 className={styles.heading}>{copy.notFound}</h1>
        <p className={styles.empty}>{copy.notFoundBody}</p>
        <p className={styles.actions}>
          <Link className={styles.linkButton} href="/">
            {copy.backToShop}
          </Link>
        </p>
      </main>
    </ShopChrome>
  );
}
