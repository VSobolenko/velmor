/** Category tile image from slug heuristics; photography is the generic fallback. */

export function categoryImageSrc(slug: string): string {
  const normalized = slug.toLowerCase();
  if (
    normalized.includes("illustrat") ||
    normalized.includes("vector") ||
    normalized.includes("draw") ||
    normalized.includes("ілюстр") ||
    normalized.includes("иллюстр")
  ) {
    return "/brand/category-illustration.png";
  }
  return "/brand/category-photography.png";
}

export const HERO_IMAGE_SRC = "/brand/proofbasket-hero.png";
