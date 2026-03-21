import { Skeleton } from '@/components/ui/skeleton'

interface TableSkeletonProps {
  rows?: number
}

export function TableSkeleton({ rows = 5 }: TableSkeletonProps) {
  return (
    <div className="w-full">
      {/* Header row */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
        <Skeleton className="h-4 w-4 rounded" />
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-4 w-24 ml-auto" />
      </div>
      {/* Data rows */}
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-3 px-4 py-3 border-b border-gray-50 dark:border-gray-700/50"
        >
          <Skeleton className="h-4 w-4 rounded" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-5 w-20 rounded-full" />
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-24 ml-auto" />
        </div>
      ))}
    </div>
  )
}

interface CardSkeletonProps {
  cards?: number
}

export function CardSkeleton({ cards = 4 }: CardSkeletonProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: cards }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl border border-gray-100 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 space-y-3"
        >
          <div className="flex items-center justify-between">
            <Skeleton className="h-5 w-24" />
            <Skeleton className="h-5 w-16 rounded-full" />
          </div>
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <div className="flex items-center gap-2 pt-1">
            <Skeleton className="h-7 w-16 rounded" />
            <Skeleton className="h-7 w-16 rounded" />
          </div>
        </div>
      ))}
    </div>
  )
}
