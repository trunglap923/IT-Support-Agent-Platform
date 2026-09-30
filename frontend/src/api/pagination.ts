export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
}

export function paginatedUrl(
  path: string,
  params: Record<string, string> = {},
  cursor: string | null = null,
  limit = 20,
): string {
  const query = new URLSearchParams({ ...params, limit: String(limit) });
  if (cursor) query.set("cursor", cursor);
  return `${path}?${query.toString()}`;
}
