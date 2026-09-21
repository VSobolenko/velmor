import be from "./be.json" with { type: "json" };
import en from "./en.json" with { type: "json" };
import ru from "./ru.json" with { type: "json" };

/**
 * The locale vocabulary. `ru` is the default, `be` and `en` are first class, and
 * `LOCALES` is the only place the set is written down.
 */
export const LOCALES = ["ru", "be", "en"] as const;

export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "ru";

/** The preference cookie, written by the switcher and read by the proxy. */
export const LOCALE_COOKIE = "pb_locale";

/** One year, in seconds. */
export const LOCALE_COOKIE_MAX_AGE = 31_536_000;

/** Request header the proxy sets so any server component can read the locale. */
export const LOCALE_HEADER = "x-pb-locale";

/**
 * `ru` is the shape of the dictionary. `DICTIONARIES` is typed `Record<Locale, Dictionary>`,
 * so a key missing in `be` or `en` fails the type check, and `scripts/check-i18n.mjs` fails
 * the lint run for a key that only one file has.
 */
export type Dictionary = typeof ru;

const DICTIONARIES: Record<Locale, Dictionary> = { ru, be, en };

export function isLocale(value: unknown): value is Locale {
  return (
    typeof value === "string" && (LOCALES as readonly string[]).includes(value)
  );
}

/**
 * A total function for values the route already validated: `[locale]/layout.tsx` calls
 * `notFound()` for an unsupported segment, so a page can fall back to the default here.
 */
export function resolveLocale(value: unknown): Locale {
  return isLocale(value) ? value : DEFAULT_LOCALE;
}

export function dictionaryFor(locale: Locale): Dictionary {
  return DICTIONARIES[locale];
}

/**
 * Locale negotiation order: a parseable cookie, then the highest-quality supported
 * language in `Accept-Language`, then `ru`.
 */
export function negotiate(
  acceptLanguage: string | null,
  cookie: string | null,
): Locale {
  const fromCookie = localeFromCookie(cookie);
  if (fromCookie !== null) {
    return fromCookie;
  }
  const fromHeader = localeFromAcceptLanguage(acceptLanguage);
  if (fromHeader !== null) {
    return fromHeader;
  }
  return DEFAULT_LOCALE;
}

/**
 * Accepts the bare cookie value (`be`) or the request-header form
 * (`pb_locale=be; other=1`). Anything unrecognised is absent, never a guess.
 */
function localeFromCookie(cookie: string | null): Locale | null {
  if (cookie === null) {
    return null;
  }
  const trimmed = cookie.trim();
  if (trimmed === "") {
    return null;
  }
  const withoutName = trimmed.startsWith(`${LOCALE_COOKIE}=`)
    ? trimmed.slice(LOCALE_COOKIE.length + 1)
    : trimmed;
  const [value = ""] = withoutName.split(";");
  const candidate = value.trim().toLowerCase();
  return isLocale(candidate) ? candidate : null;
}

/** `be-BY,ru;q=0.8,en;q=0.5` resolves to `be`; quality 0 excludes a language. */
function localeFromAcceptLanguage(header: string | null): Locale | null {
  if (header === null) {
    return null;
  }
  const parts = header.split(",");
  const ranked: { locale: Locale; quality: number; order: number }[] = [];
  for (let order = 0; order < parts.length; order += 1) {
    const [tag = "", ...parameters] = parts[order].split(";");
    const quality = qualityOf(parameters);
    if (quality <= 0) {
      continue;
    }
    const locale = localeForTag(tag.trim().toLowerCase());
    if (locale === null) {
      continue;
    }
    ranked.push({ locale, quality, order });
  }
  if (ranked.length === 0) {
    return null;
  }
  ranked.sort(
    (left, right) => right.quality - left.quality || left.order - right.order,
  );
  return ranked[0].locale;
}

function qualityOf(parameters: readonly string[]): number {
  for (const parameter of parameters) {
    const [name = "", value = ""] = parameter.split("=");
    if (name.trim().toLowerCase() !== "q") {
      continue;
    }
    const quality = Number.parseFloat(value.trim());
    return Number.isNaN(quality) ? 0 : quality;
  }
  return 1;
}

/** A tag matches on its primary subtag, so `en-GB` is `en` and `zh-CN` is nothing. */
function localeForTag(tag: string): Locale | null {
  if (isLocale(tag)) {
    return tag;
  }
  const [primary = ""] = tag.split("-");
  return isLocale(primary) ? primary : null;
}
