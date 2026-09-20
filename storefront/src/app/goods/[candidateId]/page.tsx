import { notFound } from "next/navigation";
import { AddToCartButton } from "@/components/AddToCartButton";
import { ShopChrome } from "@/components/ShopChrome";
import { CommerceApiClient, CommerceApiError } from "@/lib/api";
import { copy } from "@/lib/copy";
import styles from "../../shop.module.css";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ candidateId: string }>;
};

export default async function GoodPage({ params }: Props) {
  const { candidateId } = await params;
  const client = CommerceApiClient.fromEnv();
  let good;
  try {
    good = await client.getGood(candidateId);
  } catch (error) {
    if (error instanceof CommerceApiError && error.status === 404) {
      notFound();
    }
    throw error;
  }

  const licenseLabel =
    good.license_id === null ? copy.noLicence : good.license_id;

  return (
    <ShopChrome tagline={copy.product}>
      <main className={styles.main}>
        <h1 className={styles.heading}>{good.title}</h1>
        <p className={styles.meta}>
          {good.creator === null ? copy.unknownCreator : good.creator}
        </p>
        <p className={styles.price}>
          {good.unit_amount} {good.currency}
        </p>
        <p className={styles.license}>{copy.licence}</p>
        <p className={styles.licenseValue}>{licenseLabel}</p>
        <p className={styles.license}>{copy.obligations}</p>
        {good.obligations.length === 0 ? (
          <p className={styles.empty}>{copy.noObligations}</p>
        ) : (
          <ul className={styles.obligations}>
            {good.obligations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
        <div className={styles.actions}>
          <AddToCartButton
            candidateId={good.candidate_id}
            title={good.title}
            unitAmount={good.unit_amount}
            currency={good.currency}
          />
        </div>
      </main>
    </ShopChrome>
  );
}
