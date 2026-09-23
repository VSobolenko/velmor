"use client";

import { useEffect, useRef, useState } from "react";
import { AddToCartButton } from "./AddToCartButton";
import { PriceTag } from "./ui/PriceTag";
import type { Dictionary } from "@/lib/i18n";

type Props = {
  candidateId: string;
  title: string;
  unitAmount: string;
  currency: string;
  dict: Dictionary;
  /**
   * The ids of the in-flow add-to-cart controls this bar mirrors (the buy box action). It
   * shows only while none of them is on screen, so it never offers a second copy of a
   * control the buyer can already see.
   */
  anchorIds: readonly string[];
};

/** The bar is about 61 px tall; hide it before the footer could slide under it. */
const FOOTER_CLEARANCE = "0px 0px 64px 0px";

/**
 * The mobile action bar: compact, at the bottom, so the price and the add-to-cart stay
 * reachable while the buyer reads the details.
 *
 * `fixed` rather than `sticky`, because `html, body { overflow-x: hidden }` in `globals.css`
 * makes `body` a scroll container, which silently disables `position: sticky` for every
 * descendant (measured: the header's `sticky top-0` scrolls away too). A fixed bar takes no
 * flow space, so a sentinel rendered at the end of the content hides it just as the footer
 * arrives: the footer is never covered. Hidden from `md`, where the buy box stays in view.
 *
 * Visibility follows the in-flow actions as well as the footer: the bar is hidden while an
 * anchor is on screen, which is what keeps it from duplicating a visible control (audit
 * finding 14). Until the observer reports, the initial state assumes an anchor is on screen,
 * so the bar does not flash on first paint.
 */
export function StickyBuyBar({
  candidateId,
  title,
  unitAmount,
  currency,
  dict,
  anchorIds,
}: Props) {
  const sentinel = useRef<HTMLDivElement>(null);
  const [anchorVisible, setAnchorVisible] = useState(anchorIds.length > 0);
  const [footerVisible, setFooterVisible] = useState(false);

  useEffect(() => {
    const nodes = anchorIds
      .map((id) => document.getElementById(id))
      .filter((node): node is HTMLElement => node !== null);
    if (nodes.length === 0) {
      // No in-flow action to mirror: the bar is the only way to add, so it stays available.
      return;
    }
    const intersecting = new Set<Element>();
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          intersecting.add(entry.target);
        } else {
          intersecting.delete(entry.target);
        }
      }
      setAnchorVisible(intersecting.size > 0);
    });
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, [anchorIds]);

  useEffect(() => {
    const node = sentinel.current;
    if (node === null) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => setFooterVisible(entries[0].isIntersecting),
      { rootMargin: FOOTER_CLEARANCE },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const visible = !anchorVisible && !footerVisible;

  return (
    <>
      <div ref={sentinel} aria-hidden="true" className="h-px md:hidden" />
      {visible ? (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/95 backdrop-blur md:hidden">
          <div className="flex items-center gap-3 px-gutter py-2">
            <PriceTag amount={unitAmount} currency={currency} />
            <div className="ml-auto">
              <AddToCartButton
                candidateId={candidateId}
                title={title}
                unitAmount={unitAmount}
                currency={currency}
                label={dict["product.addToCart"]}
                addedLabel={dict["product.addedToCart"]}
                size="md"
              />
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
