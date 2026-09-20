import Link from "next/link";
import styles from "@/app/shop.module.css";

type Props = {
  tagline: string;
};

/** Shared header: brand + Home / Cart / Account. */
export function ShopChrome({ tagline }: Props) {
  return (
    <header className={styles.header}>
      <p className={styles.brand}>
        <Link href="/">Proofbasket</Link>
      </p>
      <p className={styles.tagline}>{tagline}</p>
      <nav className={styles.nav}>
        <Link href="/">Home</Link>
        <Link href="/cart">Cart</Link>
        <Link href="/account">Account</Link>
      </nav>
    </header>
  );
}
