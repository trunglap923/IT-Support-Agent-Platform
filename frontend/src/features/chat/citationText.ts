export function normalizeCitationExcerpt(excerpt: string) {
  return excerpt
    .replace(/(^|\s)#{1,6}\s+/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}
