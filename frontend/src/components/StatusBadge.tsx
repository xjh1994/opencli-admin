import { clsx } from 'clsx'

const STATUS_STYLES: Record<string, string> = {
  pending:       'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
  running:       'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  ai_processing: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
  completed:     'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
  failed:        'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
  cancelled:     'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  online:        'bg-green-100 text-green-800',
  offline:       'bg-gray-100 text-gray-700',
  sent:          'bg-green-100 text-green-800',
  raw:           'bg-gray-100 text-gray-700',
  normalized:    'bg-blue-100 text-blue-800',
  ai_processed:  'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
}

const STATUS_LABELS: Record<string, string> = {
  pending:       '待执行',
  running:       '采集中',
  ai_processing: 'AI 处理中',
  completed:     '已完成',
  failed:        '失败',
  cancelled:     '已取消',
  raw:           '原始',
  normalized:    '已归一化',
  ai_processed:  '已处理',
  sent:          '已发送',
  online:        '在线',
  offline:       '离线',
}

interface Props {
  status: string
  className?: string
}

export default function StatusBadge({ status, className }: Props) {
  const style = STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-700'
  const label = STATUS_LABELS[status] ?? status
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
        style,
        className
      )}
    >
      {label}
    </span>
  )
}
