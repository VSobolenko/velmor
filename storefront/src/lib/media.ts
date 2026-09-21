/**
 * The URL a buyer's browser loads a good's preview from.
 *
 * The browser is never pointed at the API host. `/media/preview/{id}` is a Next route
 * handler that proxies the API preview and passes its status and content type through
 * (contract.md, "Storefront media route"). A plain `<img>` consumes it rather than
 * `next/image`, which would re-encode an already optimised WebP.
 *
 * This is not a page, so it takes no locale prefix: the preview bytes are the same in
 * every language.
 */
export function previewSrc(candidateId: string): string {
  return `/media/preview/${encodeURIComponent(candidateId)}`;
}
