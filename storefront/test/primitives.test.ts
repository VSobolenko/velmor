import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { extname, join, relative } from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

/**
 * Invariants for the interaction primitives.
 *
 * There is no DOM test environment in this package and no runner beyond `node --test` (see
 * `package.json`), so these are source-level assertions: they check the rules that hold for
 * every primitive regardless of how it renders. They are the rules from
 * `openspec/changes/rebrand-print-room/design.md` and `.cursor/rules/07-product-surface.mdc`
 * that a machine can decide - one file per behaviour, no Radix outside `components/ui`, the
 * token set rather than a hex value, no buyer-visible literal, no `try`.
 *
 * What is deliberately NOT asserted here, because it needs a rendered page and a pointer:
 * focus restoration, the focus trap, arrow-key navigation, and whether the tooltip stays away
 * on a touch device. Those are `/ux-verify` evidence, not unit-test evidence.
 */

const srcRoot = fileURLToPath(new URL("../src/", import.meta.url));
const uiRoot = join(srcRoot, "components", "ui");

/** Each primitive and the one Radix package that file is allowed to wrap. */
const PRIMITIVES: Record<string, string> = {
  Menu: "@radix-ui/react-navigation-menu",
  Dialog: "@radix-ui/react-dialog",
  Tooltip: "@radix-ui/react-tooltip",
  Combobox: "@radix-ui/react-select",
  Checkbox: "@radix-ui/react-checkbox",
  RadioGroup: "@radix-ui/react-radio-group",
  Tabs: "@radix-ui/react-tabs",
  Accordion: "@radix-ui/react-accordion",
  Toast: "@radix-ui/react-toast",
};

/**
 * Where each primitive's accessible name comes from. `Accordion` is the one whose trigger
 * carries its own visible text, and `Tooltip` is the one that must not name its trigger at
 * all: the tooltip text is a description, so the caller's element keeps its own name.
 */
const NAME_SOURCE: Record<string, string> = {
  Menu: "aria-label={label}",
  Dialog: "aria-labelledby={titleId}",
  Combobox: "aria-label={label}",
  Checkbox: "aria-labelledby={labelId}",
  RadioGroup: "aria-label={label}",
  Tabs: "aria-label={label}",
  Accordion: "{item.question}",
  Toast: "aria-label={closeLabel}",
};

/**
 * `Tooltip` is the one primitive whose control is the caller's own element: it decorates a
 * trigger it does not render, so it cannot and must not impose a size on it. Every other
 * primitive draws its control and therefore owns its target.
 */
const CALLER_OWNS_THE_TARGET = new Set(["Tooltip"]);

const RADIX_IMPORT = /from\s+"(@radix-ui\/react-[a-z-]+)"/g;

function read(path: string): string {
  return readFileSync(path, "utf8");
}

/** Drop comments, so a comment that names a rule is not read as a violation of it. */
function withoutComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:])\/\/[^\n]*/g, "$1 ");
}

function importedPackages(source: string): string[] {
  return [...source.matchAll(RADIX_IMPORT)].map((match) => match[1]);
}

function sourcesUnder(directory: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      found.push(...sourcesUnder(path));
      continue;
    }
    if (extname(entry.name) === ".ts" || extname(entry.name) === ".tsx") {
      found.push(path);
    }
  }
  return found;
}

function primitivePath(name: string): string {
  return join(uiRoot, `${name}.tsx`);
}

function relativeToSrc(path: string): string {
  return relative(srcRoot, path).split("\\").join("/");
}

describe("one file per behaviour", () => {
  it("gives every primitive its own file wrapping exactly one Radix package", () => {
    for (const [name, radixPackage] of Object.entries(PRIMITIVES)) {
      const source = read(primitivePath(name));
      assert.ok(
        source.includes(`from "${radixPackage}"`),
        `${name}.tsx must import ${radixPackage}`,
      );
      assert.deepEqual(
        importedPackages(source),
        [radixPackage],
        `${name}.tsx must wrap exactly one Radix package`,
      );
    }
  });

  it("names the wrapped package in a header that says why it is wrapped", () => {
    for (const [name, radixPackage] of Object.entries(PRIMITIVES)) {
      const source = read(primitivePath(name));
      const header = source.slice(0, source.indexOf('from "@radix-ui/'));
      assert.ok(
        header.includes(radixPackage),
        `${name}.tsx must name the Radix package it wraps in its header`,
      );
      assert.ok(
        header.includes("Wraps"),
        `${name}.tsx must say why the behaviour is wrapped rather than hand-rolled`,
      );
    }
  });

  it("keeps every Radix import inside components/ui", () => {
    const offenders: string[] = [];
    for (const path of sourcesUnder(srcRoot)) {
      const relativePath = relativeToSrc(path);
      if (relativePath.startsWith("components/ui/")) {
        continue;
      }
      if (/@radix-ui\//.test(read(path))) {
        offenders.push(relativePath);
      }
    }
    assert.deepEqual(offenders, [], "a file outside ui/ imported a Radix package");
  });

  it("imports each Radix package from exactly one file, and the expected one", () => {
    const owners = new Map<string, string[]>();
    for (const path of sourcesUnder(srcRoot)) {
      const relativePath = relativeToSrc(path);
      for (const radixPackage of importedPackages(read(path))) {
        owners.set(radixPackage, [
          ...(owners.get(radixPackage) ?? []),
          relativePath,
        ]);
      }
    }
    for (const [radixPackage, files] of owners) {
      assert.equal(
        files.length,
        1,
        `${radixPackage} is imported by ${files.join(", ")}; it lives in one file`,
      );
      const owner = Object.entries(PRIMITIVES).find(
        ([, wrapped]) => wrapped === radixPackage,
      );
      assert.ok(owner !== undefined, `${radixPackage} has a wrapper`);
      assert.equal(files[0], `components/ui/${owner[0]}.tsx`);
    }
  });
});

describe("Sheet keeps its contract", () => {
  it("is rebuilt on Dialog and imports no Radix package itself", () => {
    const source = read(primitivePath("Sheet"));
    assert.ok(source.includes('from "./Dialog"'));
    assert.doesNotMatch(source, /@radix-ui\//);
  });

  it("keeps the props MobileNav and the header already call", () => {
    const source = read(primitivePath("Sheet"));
    for (const prop of [
      "open: boolean",
      "onClose: () => void",
      "title: string",
      "closeLabel: string",
      "className?: string",
      "children: ReactNode",
    ]) {
      assert.ok(source.includes(prop), `Sheet lost the prop "${prop}"`);
    }
    for (const pass of ["open={open}", "onClose={onClose}", "title={title}"]) {
      assert.ok(source.includes(pass), `Sheet no longer passes ${pass} through`);
    }
  });
});

describe("tokens and copy", () => {
  it("gives every primitive a 44px target, directly or through the shared Button", () => {
    assert.ok(
      read(primitivePath("Button")).includes("tap-target"),
      "the shared Button must carry the target, since the dialog dismisses through it",
    );
    for (const name of Object.keys(PRIMITIVES)) {
      if (CALLER_OWNS_THE_TARGET.has(name)) {
        continue;
      }
      const source = read(primitivePath(name));
      assert.ok(
        source.includes("tap-target") || source.includes("<Button"),
        `${name}.tsx must give its control the tap-target utility`,
      );
    }
  });

  it("adds no interactive target of its own where the caller's element is the target", () => {
    const source = read(primitivePath("Tooltip"));
    assert.doesNotMatch(
      withoutComments(source),
      /<button|onClick=/,
      "the tooltip trigger is the caller's element; it must not become a second control",
    );
    assert.ok(
      source.includes("tabIndex={0}"),
      "the trigger defaults to a tab stop, so the tooltip is reachable by keyboard",
    );
  });

  it("names a token, never a hex colour", () => {
    for (const name of Object.keys(PRIMITIVES)) {
      const source = read(primitivePath(name));
      assert.doesNotMatch(
        source,
        /#[0-9a-fA-F]{3,8}\b/,
        `${name}.tsx must use a token class, not a hex value`,
      );
      assert.doesNotMatch(source, /rgba?\(/);
    }
  });

  it("takes every copy attribute from a prop", () => {
    const literalCopy =
      /\b(aria-label|placeholder|alt)\s*=\s*["'][^"']*[A-Za-z][^"']*["']/;
    for (const name of Object.keys(PRIMITIVES)) {
      assert.doesNotMatch(
        withoutComments(read(primitivePath(name))),
        literalCopy,
        `${name}.tsx has a literal accessible name or placeholder`,
      );
    }
  });

  it("carries no Cyrillic and no hardcoded language", () => {
    for (const path of sourcesUnder(join(srcRoot, "components", "ui"))) {
      const source = read(path);
      assert.doesNotMatch(source, /[\u0400-\u04FF]/);
      assert.doesNotMatch(source, /lang\s*=\s*["'](ru|be|en)["']/);
    }
  });

  it("wires a name on every control that has one to wire", () => {
    for (const [name, nameSource] of Object.entries(NAME_SOURCE)) {
      assert.ok(
        read(primitivePath(name)).includes(nameSource),
        `${name}.tsx must take its accessible name from ${nameSource}`,
      );
    }
  });

  it("keeps the tooltip a description, never a name", () => {
    const source = read(primitivePath("Tooltip"));
    assert.doesNotMatch(source, /aria-label=/);
    assert.doesNotMatch(source, /aria-labelledby=/);
    assert.ok(
      source.includes("never a name"),
      "Tooltip.tsx must state that it does not name its trigger",
    );
  });
});

describe("error handling and motion", () => {
  it("contains no try/catch", () => {
    for (const name of Object.keys(PRIMITIVES)) {
      const source = withoutComments(read(primitivePath(name)));
      assert.doesNotMatch(source, /\btry\s*\{/, `${name}.tsx must not catch`);
      assert.doesNotMatch(source, /\bcatch\s*\(/, `${name}.tsx must not catch`);
    }
  });

  it("adds no keyframe animation, so there is no motion to switch off", () => {
    for (const name of Object.keys(PRIMITIVES)) {
      assert.doesNotMatch(
        read(primitivePath(name)),
        /@keyframes/,
        `${name}.tsx must not add a keyframe animation`,
      );
    }
  });
});

describe("the toast live region", () => {
  it("renders one viewport and adds no live region of its own", () => {
    const source = read(primitivePath("Toast"));
    assert.equal(
      (source.match(/ToastPrimitive\.Viewport/g) ?? []).length,
      1,
      "a second viewport is a second region",
    );
    assert.doesNotMatch(
      withoutComments(source),
      /aria-live/,
      "the polite region is the one Radix renders for the provider; a second competes with it",
    );
    assert.ok(
      source.includes('type="background"'),
      "a background toast is the polite variant",
    );
  });

  it("mounts the provider from the locale layout, with dictionary labels", () => {
    const source = read(join(srcRoot, "app", "[locale]", "layout.tsx"));
    assert.ok(source.includes('from "@/components/ui/Toast"'));
    assert.ok(source.includes("<ToastProvider"));
    assert.ok(source.includes('dict["toast.announceLabel"]'));
    assert.ok(source.includes('dict["toast.regionLabel"]'));
    assert.ok(source.includes('dict["common.close"]'));
  });
});
