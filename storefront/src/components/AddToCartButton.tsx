"use client";

import { useRouter } from "next/navigation";
import { addToCart } from "@/lib/cart";
import styles from "@/app/shop.module.css";

type Props = {
  candidateId: string;
  title: string;
  unitAmount: string;
  currency: string;
};

export function AddToCartButton({
  candidateId,
  title,
  unitAmount,
  currency,
}: Props) {
  const router = useRouter();

  function onClick() {
    addToCart({
      candidate_id: candidateId,
      unit_amount: unitAmount,
      quantity: 1,
      currency,
      title,
    });
    router.push("/cart");
  }

  return (
    <button type="button" className={styles.button} onClick={onClick}>
      Add to cart
    </button>
  );
}
