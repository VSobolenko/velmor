# The sort control does nothing until the buyer also presses "Найти"

Measured on the running shop, in a browser, on `/ru/catalogue`:

- The sort select holds five options: "Сначала новые", "Цена: по возрастанию",
  "Цена: по убыванию", "Название: А–Я", "Название: Я–А".
- Choosing "Название: А–Я" leaves the URL at `/catalogue` and leaves the grid in the same
  order: `Отель Ca' Sagredo на`, `Биткоин V2 — цифрова`, `Арпантаж: измерение`,
  `Британские гелиограф`.
- The filter form's submit controls are `Найти` and `Фильтры`. The sort therefore applies
  only when the buyer also presses `Найти`.
- Loading `/ru/catalogue?sort=title_asc` directly does reorder the grid:
  `A Hard Rain’s Gonna`, `Brexit: шрифтовая ко`, `Endiandra xanthocarp`, `Kilburn Grange Cinem`.

So the server side is correct and the control is inert. Sorting is a single-choice control that a
buyer expects to take effect the moment it is chosen; requiring a separate press for it, when the
same press is also the only way to apply the text query, reads as broken.

## The change

Making a choice in the sort control must apply that choice immediately, without pressing `Найти`.

- The URL stays the source of truth for the catalogue state. The rendered page is server-side and
  the query string must remain shareable and reloadable, so apply the change by navigating to the
  catalogue with the new `sort` value rather than by reordering the DOM in place.
- Keep the `Найти` button for the text query and for the category and licence filters. Do not
  change their behaviour in this task.
- Keep the existing query-parameter names and the existing sorting behaviour. Do not rename a
  parameter, do not add one, and do not touch the API.
- Applying the sort must carry the buyer's other current filter values, so choosing a sort does not
  silently clear the search text or the chosen category. Read
  `storefront/src/components/catalogue-query.ts` for how the parameters are built and reused, and
  build the destination from the same values the page already holds.

### Files

Read `storefront/src/components/CatalogueFilters.tsx` and
`storefront/src/components/catalogue-query.ts` first; the mechanism you need may already exist
there, reused from another control.

You may WRITE only these files:

- `storefront/src/components/CatalogueFilters.tsx`
- `storefront/src/components/ui/Select.tsx`

If the change genuinely requires a third file, stop and reply `BLOCKED <why>`. Do not edit a file
outside that list.

You may READ anything under `storefront/src/`.

## Hard rules

- Every buyer-visible string stays in the three dictionaries. A new literal in a component is a
  defect.
- Do not change any user-facing string and do not rename a dictionary key.
- Do not add a dependency. No `TODO`. Do not run git. Nothing that reaches the network.
- Keep keyboard operability and the accessible name of every control.
- `npm --prefix storefront run build` runs a type check and must pass. `npm --prefix storefront run
  lint` does not run a type check, so it is not a substitute.
- **Do not ask me to confirm a design and do not end with a question.** Implement the change.

## Verification boundary

Run exactly these, in this order, and no others:

```
npm --prefix storefront run check:i18n
npm --prefix storefront run build
```

Do not retry a failure. If a command fails, stop and report it.

## Reply contract

On success reply with exactly:

```
DONE <comma-separated list of files you changed>
```

On failure reply with exactly:

```
BLOCKED <one-line reason>
```
