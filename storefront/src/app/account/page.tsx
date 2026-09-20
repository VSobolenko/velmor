import Link from "next/link";
import { ShopChrome } from "@/components/ShopChrome";
import styles from "../shop.module.css";

export default function AccountPage() {
  return (
    <div className={styles.page}>
      <ShopChrome tagline="Account" />
      <main className={styles.main}>
        <h1 className={styles.heading}>Account</h1>
        <p className={styles.meta}>
          Buyer identity is the demo header{" "}
          <code>NEXT_PUBLIC_BUYER_ID</code> until real auth arrives.
        </p>
        <ul className={styles.list}>
          <li>
            <Link href="/account/orders">Orders</Link>
            <p className={styles.meta}>Order history for this buyer</p>
          </li>
          <li>
            <Link href="/account/entitlements">Entitlements</Link>
            <p className={styles.meta}>Downloads for paid goods</p>
          </li>
        </ul>
      </main>
    </div>
  );
}
