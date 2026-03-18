import { clsx } from 'clsx'

export default function LoadingSpinner({ className }: { className?: string }) {
  return (
    <div
      className={clsx(
        'inline-block animate-spin rounded-full border-2 border-current border-t-transparent text-blue-500',
        className ?? 'h-6 w-6'
      )}
      role="status"
      aria-label="Loading"
    />
  )
}

export function PageLoader() {
  return (
    <div className="flex items-center justify-center h-48">
      <LoadingSpinner className="h-8 w-8" />
    </div>
  )
}
