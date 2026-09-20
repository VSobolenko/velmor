import Link from "next/link";
import { notFound } from "next/navigation";
import { ShopChrome } from "@/components/ShopChrome";
import { CommerceApiClient, CommerceApiError } from "@/lib/api";
import styles from "../../shop.module.css";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ slug: string }>;
};

export default async function CategoryPage({ params }: Props) {
  const { slug } = await params;
  const client = CommerceApiClient.fromEnv();
  let category;
  try {
    category = await client.getCategory(slug);
  } catch (error) {
    if (error instanceof CommerceApiError && error.status === 404) {
      notFound();
    }
    throw error;
  }

  return (
    <div className={styles.page}>
      <ShopChrome tagline={category.name} />
      <main className={styles.main}>
        <h1 className={styles.heading}>{category.name}</h1>
        {category.goods.length === 0 ? (
          <p className={styles.empty}>This category has no goods yet.</p>
        ) : (
          <ul className={styles.list}>
            {category.goods.map((good) => (
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
      </main>
    </div>
  );
}
