import { clsx } from 'clsx'

interface Props {
  children: React.ReactNode
  className?: string
  padding?: boolean
}

export default function Card({ children, className, padding = true }: Props) {
  return (
    <div
      className={clsx(
        'bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm',
        padding && 'p-5',
        className
      )}
    >
      {children}
    </div>
  )
}
