import Link from "next/link";
import styles from "@/app/shop.module.css";
import { copy } from "@/lib/copy";
import { ShopFooter } from "./ShopFooter";

type Props = {
  tagline: string;
  children: React.ReactNode;
  hero?: React.ReactNode;
};

/** Shared chrome: header, optional hero, main children, footer with payment marks. */
export function ShopChrome({ tagline, children, hero }: Props) {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <p className={styles.brand}>
          <Link href="/">{copy.brand}</Link>
        </p>
        <p className={styles.tagline}>{tagline}</p>
        <nav className={styles.nav}>
          <Link href="/">{copy.navHome}</Link>
          <Link href="/cart">{copy.navCart}</Link>
          <Link href="/account">{copy.navAccount}</Link>
        </nav>
      </header>
      {hero ?? null}
      {children}
      <ShopFooter />
    </div>
  );
}
