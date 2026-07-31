const DEFAULT_PAGE = 1;
const DEFAULT_PAGE_SIZE = 12;
const MAX_PAGE_SIZE = 50;

function clampedInteger(value: string | null, fallback: number, maximum?: number) {
  if (value === null || value.trim() === "") return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  const integer = Math.max(1, Math.trunc(parsed));
  return maximum === undefined ? integer : Math.min(integer, maximum);
}

export function paginationFromSearch(searchStr: string) {
  const search = new URLSearchParams(searchStr);
  return {
    page: clampedInteger(search.get("page"), DEFAULT_PAGE),
    pageSize: clampedInteger(
      search.get("page_size"),
      DEFAULT_PAGE_SIZE,
      MAX_PAGE_SIZE
    )
  };
}
