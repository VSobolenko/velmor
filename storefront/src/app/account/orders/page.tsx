import Link from "next/link";
import { ShopChrome } from "@/components/ShopChrome";
import {
  CommerceApiClient,
  CommerceApiError,
  type Order,
} from "@/lib/api";
import { copy } from "@/lib/copy";
import styles from "../../shop.module.css";

export const dynamic = "force-dynamic";

type OrdersData =
  | { kind: "ok"; orders: Order[] }
  | { kind: "error"; message: string };

async function loadOrders(): Promise<OrdersData> {
  const client = CommerceApiClient.fromEnv();
  const orders = await client.listOrders();
  return { kind: "ok", orders };
}

export default async function OrdersPage() {
  let data: OrdersData;
  try {
    data = await loadOrders();
  } catch (error) {
    if (error instanceof CommerceApiError) {
      data = { kind: "error", message: error.detail };
    } else if (error instanceof Error) {
      data = { kind: "error", message: error.message };
    } else {
      data = { kind: "error", message: copy.ordersUnavailable };
    }
  }

  return (
    <ShopChrome tagline={copy.orders}>
      <main className={styles.main}>
        <h1 className={styles.heading}>{copy.orders}</h1>
        <p className={styles.status}>
          <Link href="/account">{copy.backToAccount}</Link>
        </p>
        {data.kind === "error" ? (
          <p className={styles.error}>{data.message}</p>
        ) : data.orders.length === 0 ? (
          <p className={styles.empty}>{copy.noOrders}</p>
        ) : (
          <ul className={styles.list}>
            {data.orders.map((order) => (
              <li key={order.order_id}>
                <Link
                  href={`/account/orders/${encodeURIComponent(order.order_id)}`}
                >
                  {order.order_id}
                </Link>
                <p className={styles.meta}>
                  {order.state} · {order.total} {order.currency} ·{" "}
                  {order.created_at}
                </p>
              </li>
            ))}
          </ul>
        )}
      </main>
    </ShopChrome>
  );
}
