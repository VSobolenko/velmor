import { Badge, type BadgeTone } from "@/components/ui/Badge";
import type { OrderState } from "@/lib/api/types";
import type { Dictionary } from "@/lib/i18n";

const LABEL_KEYS: Record<OrderState, keyof Dictionary> = {
  pending: "account.statePending",
  paid: "account.statePaid",
  failed: "account.stateFailed",
  cancelled: "account.stateCancelled",
  refunded: "account.stateRefunded",
};

/*
 * `accent` is deliberately unused here: it is the licence cue, and an order state sharing it
 * would read as a licence rather than as a state. `success` and `warning` keep the pair
 * distinct, and every state is also named in words, so the colour only reinforces the label.
 */
const TONES: Record<OrderState, BadgeTone> = {
  pending: "warning",
  paid: "success",
  failed: "danger",
  cancelled: "neutral",
  refunded: "neutral",
};

type Props = {
  state: OrderState;
  dict: Dictionary;
};

/** One order state as a badge, named in the active locale. Used by the account and return pages. */
export function OrderStateBadge({ state, dict }: Props) {
  return <Badge tone={TONES[state]}>{dict[LABEL_KEYS[state]]}</Badge>;
}
