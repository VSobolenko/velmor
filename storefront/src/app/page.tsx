import Image from "next/image";
import Link from "next/link";
import { ShopChrome } from "@/components/ShopChrome";
import {
  CommerceApiClient,
  CommerceApiError,
  type CatalogueGood,
  type CategorySummary,
} from "@/lib/api";
import { categoryImageSrc, HERO_IMAGE_SRC } from "@/lib/brand";
import { copy } from "@/lib/copy";
import styles from "./shop.module.css";

export const dynamic = "force-dynamic";

type HomeData =
  | {
      kind: "ok";
      categories: CategorySummary[];
      goods: CatalogueGood[];
      health: string;
    }
  | { kind: "error"; message: string };

async function loadHome(): Promise<HomeData> {
  const client = CommerceApiClient.fromEnv();
  const [categories, goods, health] = await Promise.all([
    client.listCategories(),
    client.listGoods(),
    client.getHealth(),
  ]);
  return {
    kind: "ok",
    categories,
    goods: goods.slice(0, 12),
    health: `${health.status} (${health.environment})`,
  };
}

export default async function Home() {
  let data: HomeData;
  try {
    data = await loadHome();
  } catch (error) {
    if (error instanceof CommerceApiError) {
      data = { kind: "error", message: error.detail };
    } else if (error instanceof Error) {
      data = { kind: "error", message: error.message };
    } else {
      data = { kind: "error", message: copy.catalogueUnavailable };
    }
  }

  const hero = (
    <section className={styles.hero} aria-label={copy.brand}>
      <Image
        className={styles.heroImage}
        src={HERO_IMAGE_SRC}
        alt=""
        fill
        priority
        sizes="100vw"
      />
      <div className={styles.heroOverlay} aria-hidden="true" />
      <div className={styles.heroContent}>
        <h1 className={styles.heroBrand}>{copy.brand}</h1>
        <p className={styles.heroSupport}>{copy.heroSupport}</p>
        <div className={styles.heroActions}>
          <a className={`${styles.button} ${styles.buttonAccent}`} href="#catalogue">
            {copy.catalogCta}
          </a>
        </div>
      </div>
    </section>
  );

  return (
    <ShopChrome tagline={copy.heroSupport} hero={hero}>
      <main id="catalogue" className={styles.main}>
        {data.kind === "error" ? (
          <p className={styles.error}>{data.message}</p>
        ) : (
          <>
            <h2 className={styles.heading}>{copy.categories}</h2>
            {data.categories.length === 0 ? (
              <p className={styles.empty}>{copy.noCategories}</p>
            ) : (
              <ul className={styles.categoryGrid}>
                {data.categories.map((category) => (
                  <li key={category.category_id}>
                    <Link
                      className={styles.categoryTile}
                      href={`/categories/${category.slug}`}
                    >
                      <Image
                        className={styles.categoryTileImage}
                        src={categoryImageSrc(category.slug)}
                        alt=""
                        width={480}
                        height={360}
                      />
                      <span className={styles.categoryTileLabel}>
                        {category.name}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            <h2 className={styles.subheading}>{copy.recentGoods}</h2>
            {data.goods.length === 0 ? (
              <p className={styles.empty}>{copy.noGoods}</p>
            ) : (
              <ul className={styles.list}>
                {data.goods.map((good) => (
                  <li key={good.candidate_id}>
                    <Link href={`/goods/${encodeURIComponent(good.candidate_id)}`}>
                      {good.title}
                    </Link>
                    <p className={styles.meta}>
                      {good.unit_amount} {good.currency}
                      {good.license_id !== null ? ` · ${good.license_id}` : ""}
                    </p>
                  </li>
                ))}
              </ul>
            )}
            <p className={styles.status}>{data.health}</p>
          </>
        )}
      </main>
    </ShopChrome>
  );
}
