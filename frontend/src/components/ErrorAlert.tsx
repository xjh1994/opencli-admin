import { AlertCircle } from 'lucide-react'

interface Props {
  error: Error | string
  onRetry?: () => void
}

export default function ErrorAlert({ error, onRetry }: Props) {
  const message = error instanceof Error ? error.message : error
  return (
    <div className="flex items-start gap-3 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
      <AlertCircle className="text-red-500 shrink-0 mt-0.5" size={18} />
      <div className="flex-1">
        <p className="text-sm text-red-700 dark:text-red-400">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-2 text-xs text-red-600 underline hover:no-underline"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  )
}
