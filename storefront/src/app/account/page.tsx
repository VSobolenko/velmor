import Link from "next/link";
import { ShopChrome } from "@/components/ShopChrome";
import { copy } from "@/lib/copy";
import styles from "../shop.module.css";

export default function AccountPage() {
  return (
    <ShopChrome tagline={copy.account}>
      <main className={styles.main}>
        <h1 className={styles.heading}>{copy.account}</h1>
        <p className={styles.meta}>{copy.accountDemoNote}</p>
        <ul className={styles.list}>
          <li>
            <Link href="/account/orders">{copy.orders}</Link>
            <p className={styles.meta}>{copy.ordersHint}</p>
          </li>
          <li>
            <Link href="/account/entitlements">{copy.entitlements}</Link>
            <p className={styles.meta}>{copy.entitlementsHint}</p>
          </li>
        </ul>
      </main>
    </ShopChrome>
  );
}
