import assert from "node:assert/strict";
import { readFileSync, statSync } from "node:fs";
import * as nodeModule from "node:module";
import { describe, it } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

/*
 * The brand components are `.tsx`, and Node's type stripping does not load that extension: this
 * suite is run by `node --test` with no bundler. So a synchronous loader is registered here that
 * transpiles a `.tsx` source with the TypeScript compiler that is already a devDependency, and
 * resolves the two specifiers Node cannot resolve for itself: the `@/` alias from `tsconfig.json`,
 * and `next/link`, which the Next bundler resolves but Node does not (the package publishes
 * `link.js` without a subpath export for the bare specifier).
 *
 * `registerHooks` is a Node 24 API and the installed `@types/node` is 20.x, which does not
 * declare it, so its shape is given below rather than widening the call site.
 */
type ResolveResult = { readonly url: string; readonly shortCircuit?: boolean };
type LoadResult = { readonly format: string; readonly source: string; readonly shortCircuit?: boolean };
type HookContext = { readonly parentURL?: string };

type RegisteredHooks = {
  readonly resolve: (
    specifier: string,
    context: HookContext,
    nextResolve: (specifier: string, context: HookContext) => ResolveResult,
  ) => ResolveResult;
  readonly load: (
    url: string,
    context: HookContext,
    nextLoad: (url: string, context: HookContext) => unknown,
  ) => unknown;
};

const { registerHooks } = nodeModule as unknown as {
  readonly registerHooks: (hooks: RegisteredHooks) => void;
};

const SRC_ROOT = new URL("../src/", import.meta.url);
const SOURCE_SUFFIXES = [".tsx", ".ts", ".mts", ".js", "/index.ts", "/index.tsx"];
const NEXT_LINK_URL = pathToFileURL(
  nodeModule.createRequire(import.meta.url).resolve("next/link.js"),
).href;

const TRANSPILE_OPTIONS: ts.CompilerOptions = {
  jsx: ts.JsxEmit.ReactJSX,
  module: ts.ModuleKind.ESNext,
  target: ts.ScriptTarget.ES2022,
};

/** `url` itself when it is a file, otherwise the first suffix that makes it one. */
function withSuffix(url: URL): URL | undefined {
  const candidates = [url, ...SOURCE_SUFFIXES.map((suffix) => new URL(`${url.href}${suffix}`))];
  return candidates.find((candidate) => {
    const stats = statSync(fileURLToPath(candidate), { throwIfNoEntry: false });
    return stats !== undefined && stats.isFile();
  });
}

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === "next/link") {
      return { url: NEXT_LINK_URL, shortCircuit: true };
    }
    /*
     * Only a specifier written by this project's own sources is resolved here. A relative
     * specifier inside `node_modules` is left to Node: `next` itself requires directories whose
     * resolution is CommonJS's, not this loader's.
     */
    const from = context.parentURL;
    const base =
      specifier.startsWith("@/")
        ? new URL(specifier.slice(2), SRC_ROOT)
        : specifier.startsWith(".") && from !== undefined && from.startsWith(SRC_ROOT.href)
          ? new URL(specifier, from)
          : undefined;
    const resolved = base === undefined ? undefined : withSuffix(base);
    return resolved === undefined
      ? nextResolve(specifier, context)
      : { url: resolved.href, shortCircuit: true };
  },
  load(url, context, nextLoad) {
    if (!url.endsWith(".tsx")) {
      return nextLoad(url, context);
    }
    const path = fileURLToPath(url);
    const transpiled: LoadResult = {
      format: "module",
      source: ts.transpileModule(readFileSync(path, "utf8"), {
        compilerOptions: TRANSPILE_OPTIONS,
        fileName: path,
      }).outputText,
      shortCircuit: true,
    };
    return transpiled;
  },
});

const { Hallmark, HallmarkBadge, HallmarkMedallion, HallmarkRule, Wordmark } = await import(
  "../src/components/brand/index.ts"
);

/** The span the wordmark hides from the accessibility tree, and the span that names it. */
const VISUAL_PREFIX = '<span aria-hidden="true">';
const NAME_PREFIX = '<span class="sr-only select-none">';

function render(element: ReactElement): string {
  return renderToStaticMarkup(element);
}

/** The markup of the visible arrangement, which is not the part a screen reader is given. */
function visualPart(markup: string): string {
  const start = markup.indexOf(VISUAL_PREFIX);
  const end = markup.indexOf(NAME_PREFIX);
  assert.ok(start !== -1, `no visual arrangement in ${markup}`);
  assert.ok(end > start, `no hidden name in ${markup}`);
  return markup.slice(start, end);
}

/** What a browser copies out of a fragment of markup: its text nodes, concatenated. */
function textOf(markup: string): string {
  return markup.replace(/<[^>]*>/g, "");
}

/** The name the accessibility tree is given, read from the visually hidden span. */
function announcedName(markup: string): string {
  const start = markup.indexOf(NAME_PREFIX);
  assert.ok(start !== -1, `no hidden name in ${markup}`);
  const rest = markup.slice(start + NAME_PREFIX.length);
  return rest.slice(0, rest.indexOf("<"));
}

function occurrences(haystack: string, needle: string): number {
  return haystack.split(needle).length - 1;
}

/** The first tag in the markup that matches `pattern`. */
function firstTag(markup: string, pattern: RegExp): string {
  const match = markup.match(pattern);
  assert.ok(match !== null, `no tag matching ${pattern.source} in ${markup}`);
  return match[0];
}

function attribute(tag: string, name: string): number {
  const match = tag.match(new RegExp(`(?:^|\\s)${name}="([-0-9.]+)"`));
  assert.ok(match !== null, `no ${name} in ${tag}`);
  return Number(match[1]);
}

/** The mark's viewBox side, read from the markup rather than assumed. */
function viewBoxSide(markup: string): number {
  const match = markup.match(/viewBox="0 0 ([\d.]+) [\d.]+"/);
  assert.ok(match !== null, `no square viewBox in ${markup}`);
  return Number(match[1]);
}

type DrawnLine = {
  readonly slope: 1 | -1;
  /** How far the line sits from the centre of the viewBox, along the diagonal it crosses. */
  readonly offset: number;
  readonly ends: readonly (readonly [number, number])[];
};

/** Every stroke in a mark, positioned by the offset that places it in the weave. */
function drawnLines(markup: string): readonly DrawnLine[] {
  const side = viewBoxSide(markup);
  return [...markup.matchAll(/<line\b[^>]*>/g)].map((match) => {
    const tag = match[0];
    const x1 = attribute(tag, "x1");
    const y1 = attribute(tag, "y1");
    const x2 = attribute(tag, "x2");
    const y2 = attribute(tag, "y2");
    const slope: 1 | -1 = (x2 - x1) * (y2 - y1) > 0 ? 1 : -1;
    return {
      slope,
      offset: slope === 1 ? x1 - y1 : x1 + y1 - side,
      ends: [
        [x1, y1],
        [x2, y2],
      ],
    };
  });
}

describe("Hallmark", () => {
  it("names itself when it is given a meaning", () => {
    const markup = render(createElement(Hallmark, { title: "Rights checked" }));
    assert.match(markup, /role="img"/);
    assert.match(markup, /<title>Rights checked<\/title>/);
    assert.doesNotMatch(markup, /aria-hidden/);
  });

  it("hides itself when it is decoration", () => {
    const markup = render(createElement(Hallmark, {}));
    assert.match(markup, /aria-hidden="true"/);
    assert.doesNotMatch(markup, /role="img"/);
    assert.doesNotMatch(markup, /<title>/);
  });

  it("draws a frame, six weave strokes and the register corner", () => {
    const markup = render(createElement(Hallmark, {}));
    const frame = firstTag(markup, /<rect\b[^>]*rx="1.5"[^>]*>/);
    assert.equal(attribute(frame, "x"), 0.75);
    assert.equal(attribute(frame, "y"), 0.75);
    assert.equal(attribute(frame, "width"), 22.5);
    assert.equal(attribute(frame, "height"), 22.5);
    assert.match(markup, /stroke-width="1.5"/);
    const register = firstTag(markup, /<rect\b[^>]*fill="currentColor"[^>]*>/);
    assert.equal(attribute(register, "x"), 16);
    assert.equal(attribute(register, "y"), 16);
    assert.equal(attribute(register, "width"), 4);
    assert.equal(attribute(register, "height"), 4);
    assert.equal(drawnLines(markup).length, 6);
  });

  it("spaces the weave evenly and symmetrically, inside the frame", () => {
    const markup = render(createElement(Hallmark, {}));
    const frame = firstTag(markup, /<rect\b[^>]*rx="1.5"[^>]*>/);
    const inside = attribute(frame, "x");
    const outside = inside + attribute(frame, "width");
    for (const slope of [1, -1] as const) {
      const offsets = drawnLines(markup)
        .filter((line) => line.slope === slope)
        .map((line) => line.offset)
        .sort((left, right) => left - right);
      assert.equal(offsets.length, 3, "a family does not have three strokes");
      assert.equal(offsets[1] - offsets[0], offsets[2] - offsets[1], "the spacing is not even");
      assert.equal(offsets[0] + offsets[2], 0, "the family is not symmetric about the centre");
    }
    for (const line of drawnLines(markup)) {
      for (const [x, y] of line.ends) {
        assert.ok(x >= inside && x <= outside, `a weave stroke leaves the frame at x=${x}`);
        assert.ok(y >= inside && y <= outside, `a weave stroke leaves the frame at y=${y}`);
      }
    }
  });
});

describe("HallmarkMedallion", () => {
  it("names itself when it is given a meaning, and hides itself otherwise", () => {
    const named = render(createElement(HallmarkMedallion, { title: "Rights checked" }));
    assert.match(named, /role="img"/);
    assert.match(named, /<title>Rights checked<\/title>/);
    const decoration = render(createElement(HallmarkMedallion, {}));
    assert.match(decoration, /aria-hidden="true"/);
    assert.doesNotMatch(decoration, /role="img"/);
  });

  it("draws a ring with the weave's cross inside it", () => {
    const markup = render(createElement(HallmarkMedallion, {}));
    const circle = firstTag(markup, /<circle\b[^>]*>/);
    const centre = attribute(circle, "cx");
    const radius = attribute(circle, "r");
    assert.equal(attribute(circle, "cy"), centre);
    assert.equal(radius, viewBoxSide(markup) / 2 - 0.75);
    const strokes = drawnLines(markup);
    assert.equal(strokes.length, 2);
    assert.deepEqual(
      strokes.map((line) => line.slope).sort(),
      [-1, 1],
      "the cross is not the weave's two directions",
    );
    for (const line of strokes) {
      for (const [x, y] of line.ends) {
        const reach = Math.hypot(x - centre, y - centre);
        assert.ok(reach < radius, `a cross stroke leaves the ring at (${x}, ${y})`);
      }
    }
  });
});

describe("Wordmark", () => {
  const name = "Proofbasket";
  const markup = render(createElement(Wordmark, { name, locale: "ru", href: "/ru" }));

  it("announces the plain name once, and never the fragments", () => {
    assert.equal(announcedName(markup), name);
    assert.equal(occurrences(markup, name), 1, "the name is not announced exactly once");
    assert.doesNotMatch(visualPart(markup), /role="img"/);
    assert.doesNotMatch(visualPart(markup), /<title>/);
  });

  it("keeps every letter as text, so a copy of the wordmark is the name", () => {
    const visual = visualPart(markup);
    assert.equal(textOf(visual), name);
    assert.equal(occurrences(visual, "opacity-0"), 2, "a glyph is not laid out as text");
    assert.equal(occurrences(visual, "<svg"), 2, "one medallion per glyph replaced");
  });

  it("falls back to plain text when the name has no o", () => {
    const plain = render(createElement(Wordmark, { name: "Basket", locale: "en", href: "/en" }));
    assert.doesNotMatch(plain, /<svg/);
    assert.equal(textOf(visualPart(plain)), "Basket");
    assert.equal(announcedName(plain), "Basket");
  });

  it("draws a medallion for every o when the name has more than two", () => {
    const many = render(createElement(Wordmark, { name: "Boobook", locale: "en", href: "/en" }));
    assert.equal(occurrences(visualPart(many), "<svg"), 4);
    assert.equal(textOf(visualPart(many)), "Boobook");
    assert.equal(announcedName(many), "Boobook");
    const glyphsOnly = render(createElement(Wordmark, { name: "oo", locale: "en", href: "/en" }));
    assert.equal(occurrences(visualPart(glyphsOnly), "<svg"), 2);
    assert.equal(textOf(visualPart(glyphsOnly)), "oo");
    assert.equal(announcedName(glyphsOnly), "oo");
  });

  it("links home in the active locale, at the requested size", () => {
    const large = render(
      createElement(Wordmark, { name, locale: "be", href: "/be", size: "lg" }),
    );
    assert.match(large, /href="\/be"/);
    assert.match(large, /lang="be"/);
    assert.match(large, /text-4xl/);
  });
});

describe("HallmarkRule", () => {
  const markup = render(createElement(HallmarkRule, {}));

  it("draws the mark in the accent over paper, on a hairline in the line colour", () => {
    assert.match(markup, /bg-line/);
    assert.match(markup, /bg-paper/);
    assert.match(markup, /text-accent/);
    assert.match(markup, /<svg/);
  });

  it("carries no text and no meaning of its own", () => {
    assert.equal(textOf(markup), "");
    assert.match(markup, /aria-hidden="true"/);
    assert.doesNotMatch(markup, /role="img"/);
  });
});

describe("HallmarkBadge", () => {
  const label = "Проверено";
  const markup = render(createElement(HallmarkBadge, { label, title: "explanation" }));

  it("shows the caller's label and writes no copy of its own", () => {
    assert.equal(textOf(markup), label);
  });

  it("uses the accent badge tokens and a decorative mark", () => {
    assert.match(markup, /bg-accent-soft/);
    assert.match(markup, /text-accent-strong/);
    assert.match(markup, /<svg/);
    assert.doesNotMatch(markup, /role="img"/);
  });

  it("forwards the optional explanation", () => {
    assert.match(markup, /title="explanation"/);
    const bare = render(createElement(HallmarkBadge, { label }));
    assert.doesNotMatch(bare, /title=/);
  });
});
