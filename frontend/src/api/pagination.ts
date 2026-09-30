export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
}

export function paginatedUrl(path: string, params: Record<string, string> = {}): string {
  const query = new URLSearchParams({ ...params, limit: "100" });
  return `${path}?${query.toString()}`;
}
