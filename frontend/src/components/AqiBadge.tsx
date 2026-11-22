import { categoryFor } from "@/lib/aqi";

/** Category label for a daily mean. The text is always shown, so colour is never the only signal. */
export function AqiBadge({ value }: { value: number }) {
  const category = categoryFor(value);
  return (
    <span
      className="inline-block rounded px-2 py-0.5 text-xs font-semibold"
      style={{ backgroundColor: category.background, color: category.text }}
      data-category={category.key}
    >
      {category.label}
    </span>
  );
}
