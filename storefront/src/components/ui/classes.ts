/** Join class name parts, dropping the ones a caller left out. */
export function classNames(...parts: (string | undefined)[]): string {
  return parts.filter((part) => part !== undefined && part !== "").join(" ");
}
