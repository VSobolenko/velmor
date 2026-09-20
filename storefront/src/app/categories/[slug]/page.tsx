import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ShopChrome } from "@/components/ShopChrome";
import { CommerceApiClient, CommerceApiError } from "@/lib/api";
import { categoryImageSrc } from "@/lib/brand";
import { copy } from "@/lib/copy";
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
    <ShopChrome tagline={category.name}>
      <main className={styles.main}>
        <div className={styles.categoryBanner}>
          <Image
            className={styles.categoryBannerImage}
            src={categoryImageSrc(category.slug)}
            alt=""
            width={640}
            height={280}
            priority
          />
        </div>
        <h1 className={styles.heading}>{category.name}</h1>
        {category.goods.length === 0 ? (
          <p className={styles.empty}>{copy.categoryEmpty}</p>
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
    </ShopChrome>
  );
}
