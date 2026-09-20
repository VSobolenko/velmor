import Link from "next/link";
import { notFound } from "next/navigation";
import { DownloadButton } from "@/components/DownloadButton";
import { ShopChrome } from "@/components/ShopChrome";
import { CommerceApiClient, CommerceApiError, type Order } from "@/lib/api";
import { copy } from "@/lib/copy";
import styles from "../../../shop.module.css";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ orderId: string }>;
};

export default async function OrderDetailPage({ params }: Props) {
  const { orderId } = await params;
  const client = CommerceApiClient.fromEnv();
  let order: Order;
  try {
    order = await client.getOrder(orderId);
  } catch (error) {
    if (error instanceof CommerceApiError && error.status === 404) {
      notFound();
    }
    throw error;
  }

  const isPaid = order.state === "paid";

  return (
    <ShopChrome tagline={copy.order}>
      <main className={styles.main}>
        <h1 className={styles.heading}>{order.order_id}</h1>
        <p className={styles.meta}>
          {order.state} · {order.total} {order.currency} · {order.created_at}
        </p>
        <p className={styles.status}>
          <Link href="/account/orders">{copy.allOrders}</Link>
        </p>

        <h2 className={styles.subheading}>{copy.lines}</h2>
        <ul className={styles.list}>
          {order.lines.map((line) => (
            <li key={line.candidate_id}>
              <Link href={`/goods/${encodeURIComponent(line.candidate_id)}`}>
                {line.candidate_id}
              </Link>
              <p className={styles.meta}>
                {line.quantity} × {line.unit_amount}
              </p>
            </li>
          ))}
        </ul>

        {isPaid ? (
          <>
            <h2 className={styles.subheading}>{copy.downloads}</h2>
            <p className={styles.meta}>
              {copy.orderPaidDownloadsHint}{" "}
              <Link href="/account/entitlements">{copy.entitlements}</Link>.
            </p>
            <ul className={styles.list}>
              {order.lines.map((line) => (
                <li key={`dl-${line.candidate_id}`} className={styles.cartLine}>
                  <span>{line.candidate_id}</span>
                  <div className={styles.actions}>
                    <DownloadButton candidateId={line.candidate_id} />
                  </div>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <>
            <h2 className={styles.subheading}>{copy.downloads}</h2>
            <p className={styles.empty}>{copy.orderUnpaid}</p>
          </>
        )}
      </main>
    </ShopChrome>
  );
}
