import type { Locale } from "./i18n";

/**
 * A byte count in the reader's language and units.
 *
 * `Intl` owns the unit names and the decimal separator, so nothing here is a translated
 * literal: `2524444` is `2,5 МБ` in `ru` and `2.5 MB` in `en`.
 */
export function formatFileSize(bytes: number, locale: Locale): string {
  if (bytes < 1_000) {
    return new Intl.NumberFormat(locale, {
      style: "unit",
      unit: "byte",
      maximumFractionDigits: 0,
    }).format(bytes);
  }
  if (bytes < 1_000_000) {
    return new Intl.NumberFormat(locale, {
      style: "unit",
      unit: "kilobyte",
      maximumFractionDigits: 1,
    }).format(bytes / 1_000);
  }
  return new Intl.NumberFormat(locale, {
    style: "unit",
    unit: "megabyte",
    maximumFractionDigits: 1,
  }).format(bytes / 1_000_000);
}

/** An ISO instant as a reader-facing date; the time of day is not useful on these pages. */
export function formatInstant(value: string, locale: Locale): string {
  return new Intl.DateTimeFormat(locale, { dateStyle: "long" }).format(
    new Date(value),
  );
}

/** A count with the reader's digit grouping. */
export function formatCount(value: number, locale: Locale): string {
  return new Intl.NumberFormat(locale).format(value);
}

export type FormatKey =
  | "format.image"
  | "format.audio"
  | "format.video"
  | "format.document"
  | "format.other";

/**
 * The dictionary key for the kind of file a good is. An unrecognised kind is a file, not a
 * guess: the label states the medium, and the licence and size carry the specifics.
 */
export function formatKeyFor(contentType: string): FormatKey {
  switch (contentType.toLowerCase()) {
    case "image":
      return "format.image";
    case "audio":
      return "format.audio";
    case "video":
      return "format.video";
    case "document":
      return "format.document";
    default:
      return "format.other";
  }
}
