interface PaginationProps {
  page: number
  pages: number
  total: number
  limit: number
  onChange: (page: number) => void
}

function buildPageNumbers(page: number, pages: number): (number | 'ellipsis')[] {
  if (pages <= 7) {
    return Array.from({ length: pages }, (_, i) => i + 1)
  }

  const result: (number | 'ellipsis')[] = []

  // Always show first page
  result.push(1)

  if (page <= 4) {
    // Near the start: show 1 2 3 4 5 ... N
    for (let i = 2; i <= Math.min(5, pages - 1); i++) result.push(i)
    result.push('ellipsis')
  } else if (page >= pages - 3) {
    // Near the end: show 1 ... N-4 N-3 N-2 N-1 N
    result.push('ellipsis')
    for (let i = Math.max(2, pages - 4); i <= pages - 1; i++) result.push(i)
  } else {
    // Middle: show 1 ... p-1 p p+1 ... N
    result.push('ellipsis')
    for (let i = page - 1; i <= page + 1; i++) result.push(i)
    result.push('ellipsis')
  }

  // Always show last page
  result.push(pages)

  return result
}

export default function Pagination({ page, pages, total, onChange }: PaginationProps) {
  const pageNumbers = buildPageNumbers(page, pages)

  return (
    <div className="flex items-center justify-between px-5 py-3 border-t border-gray-100 dark:border-gray-700 text-sm">
      <span className="text-gray-500">共 {total} 条</span>

      <div className="flex items-center gap-1">
        {/* Prev */}
        <button
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
          className="px-2 py-1 rounded border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label="上一页"
        >
          &lt;
        </button>

        {/* Page numbers */}
        {pageNumbers.map((p, i) =>
          p === 'ellipsis' ? (
            <span key={`ellipsis-${i}`} className="px-2 py-1 text-gray-400 select-none">
              …
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onChange(p)}
              className={`min-w-[32px] px-2 py-1 rounded border transition-colors ${
                p === page
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700'
              }`}
            >
              {p}
            </button>
          )
        )}

        {/* Next */}
        <button
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
          className="px-2 py-1 rounded border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label="下一页"
        >
          &gt;
        </button>
      </div>
    </div>
  )
}
