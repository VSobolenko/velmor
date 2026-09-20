import Link from "next/link";
import { ShopChrome } from "@/components/ShopChrome";
import {
  CommerceApiClient,
  CommerceApiError,
  type CatalogueGood,
  type CategorySummary,
} from "@/lib/api";
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
      data = { kind: "error", message: "catalogue unavailable" };
    }
  }

  return (
    <div className={styles.page}>
      <ShopChrome tagline="Goods that passed the Velmor rights gate" />
      <main className={styles.main}>
        {data.kind === "error" ? (
          <p className={styles.error}>{data.message}</p>
        ) : (
          <>
            <h1 className={styles.heading}>Categories</h1>
            {data.categories.length === 0 ? (
              <p className={styles.empty}>No categories yet.</p>
            ) : (
              <ul className={styles.list}>
                {data.categories.map((category) => (
                  <li key={category.category_id}>
                    <Link href={`/categories/${category.slug}`}>
                      {category.name}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            <h2 className={styles.subheading}>Recent goods</h2>
            {data.goods.length === 0 ? (
              <p className={styles.empty}>Nothing in the catalogue yet.</p>
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
    </div>
  );
}
