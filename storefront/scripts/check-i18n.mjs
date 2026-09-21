import { readFileSync, readdirSync } from "node:fs";
import { extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Dictionary gate. The storefront must not ship a locale with a missing key, an empty value, a
 * placeholder left behind, or an entry in `be` / `en` that is still the other language's text.
 *
 * Run by `npm run lint`, so a broken dictionary fails the same command that fails a broken
 * component.
 */

const LOCALES = ["ru", "be", "en"];

/** The language's own name is the same word in every dictionary, so Cyrillic is correct here. */
const CYRILLIC_ALLOWED_IN_EN = ["common.localeRu", "common.localeBe"];

const PLACEHOLDER_MARKERS = [
  "TODO",
  "TBD",
  "FIXME",
  "XXX",
  "PLACEHOLDER",
  "LOREM IPSUM",
  "{{",
  "%s",
];

const directory = fileURLToPath(new URL("../src/lib/i18n/", import.meta.url));
const sourceRoot = fileURLToPath(new URL("../src/", import.meta.url));

/**
 * Files that render or name UI, scanned for a user-facing string typed straight into the
 * markup. A JSX text node is recognised as ">" ... "<" with no brace, angle bracket, statement
 * punctuation or operator in between, which keeps a comparison or a generic type out; the
 * check is a net, not a parser, and a string that builds its text by concatenation still has
 * to be caught in review.
 */
const TSX_DIRECTORIES = ["app", "components"];

const JSX_TEXT = />(\s*[\p{L}][^<>{};()=+*/&|![\]]*?)\s*</gu;

function readDictionary(locale) {
  const text = readFileSync(`${directory}${locale}.json`, "utf8");
  return JSON.parse(text);
}

function entries(dictionary) {
  return Object.entries(dictionary);
}

const problems = [];
const literalProblems = [];
const dictionaries = {};

function tsxFilesUnder(directory) {
  const found = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      found.push(...tsxFilesUnder(path));
      continue;
    }
    if (extname(entry.name) === ".tsx") {
      found.push(path);
    }
  }
  return found;
}

function shorten(text) {
  const oneLine = text.split(/\s+/).join(" ");
  return oneLine.length > 60 ? `${oneLine.slice(0, 57)}...` : oneLine;
}

for (const locale of LOCALES) {
  try {
    const parsed = readDictionary(locale);
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      problems.push(`${locale}.json: the top level must be a JSON object of key/value pairs`);
      continue;
    }
    dictionaries[locale] = parsed;
  } catch (error) {
    problems.push(`${locale}.json: ${error instanceof Error ? error.message : String(error)}`);
  }
}

if (problems.length === 0) {
  const reference = dictionaries.ru;
  const referenceKeys = new Set(Object.keys(reference));

  for (const locale of LOCALES) {
    if (locale === "ru") {
      continue;
    }
    const keys = new Set(Object.keys(dictionaries[locale]));
    for (const key of referenceKeys) {
      if (!keys.has(key)) {
        problems.push(`${locale}.json: missing key "${key}"`);
      }
    }
    for (const key of keys) {
      if (!referenceKeys.has(key)) {
        problems.push(`${locale}.json: key "${key}" is not in ru.json`);
      }
    }
  }

  for (const locale of LOCALES) {
    for (const [key, value] of entries(dictionaries[locale])) {
      if (typeof value !== "string") {
        problems.push(`${locale}.json: "${key}" must be a string`);
        continue;
      }
      if (value.trim() === "") {
        problems.push(`${locale}.json: "${key}" is empty`);
        continue;
      }
      const upper = value.toUpperCase();
      for (const marker of PLACEHOLDER_MARKERS) {
        if (upper.includes(marker)) {
          problems.push(`${locale}.json: "${key}" still contains the placeholder "${marker}"`);
        }
      }
      if (locale === "en" && /\p{Script=Cyrillic}/u.test(value) && !CYRILLIC_ALLOWED_IN_EN.includes(key)) {
        problems.push(`${locale}.json: "${key}" contains Cyrillic text`);
      }
    }
  }

  for (const [key, value] of entries(dictionaries.ru)) {
    const be = dictionaries.be[key];
    const en = dictionaries.en[key];
    if (be === undefined || en === undefined) {
      continue;
    }
    if (be === en && be !== value) {
      problems.push(
        `"${key}": be and en are both "${be}" while ru is "${value}"; one of them is untranslated`,
      );
    }
  }
}

if (problems.length > 0) {
  console.error(`i18n check failed with ${problems.length} problem(s):`);
  for (const problem of problems) {
    console.error(`  - ${problem}`);
  }
  process.exit(1);
}

const components = TSX_DIRECTORIES.flatMap((name) => tsxFilesUnder(join(sourceRoot, name)));
for (const file of components) {
  const source = readFileSync(file, "utf8");
  const relativePath = relative(sourceRoot, file).split("\\").join("/");
  for (const match of source.matchAll(JSX_TEXT)) {
    const text = match[1].trim();
    if (text === "") {
      continue;
    }
    literalProblems.push(`${relativePath}: "${shorten(text)}" is a user-facing string in the markup; move it to src/lib/i18n`);
  }
}

if (literalProblems.length > 0) {
  console.error(`i18n check failed with ${literalProblems.length} literal string(s):`);
  for (const problem of literalProblems) {
    console.error(`  - ${problem}`);
  }
  process.exit(1);
}

const keyCount = Object.keys(dictionaries.ru).length;
console.log(
  `i18n check passed: ${keyCount} keys in ${LOCALES.length} locales, ${components.length} components free of literal strings`,
);
