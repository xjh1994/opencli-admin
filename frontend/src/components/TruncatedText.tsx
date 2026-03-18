import { useRef, useState } from 'react'
import { createPortal } from 'react-dom'

interface Props {
  text: string
  lines?: number
  className?: string
}

export default function TruncatedText({ text, lines = 2, className = '' }: Props) {
  const [rect, setRect] = useState<DOMRect | null>(null)
  const hideTimer = useRef<ReturnType<typeof setTimeout>>()

  const open = (e: React.MouseEvent<HTMLDivElement>) => {
    clearTimeout(hideTimer.current)
    setRect(e.currentTarget.getBoundingClientRect())
  }

  const close = () => {
    hideTimer.current = setTimeout(() => setRect(null), 120)
  }

  const keepOpen = () => clearTimeout(hideTimer.current)

  // Compute popover position: flip above if too close to bottom of viewport
  const popoverStyle = (): React.CSSProperties => {
    if (!rect) return {}
    const spaceBelow = window.innerHeight - rect.bottom
    const popoverH = 200
    const top = spaceBelow > popoverH + 12 ? rect.bottom + 6 : rect.top - popoverH - 6
    return {
      position: 'fixed',
      top,
      left: rect.left,
      width: Math.max(rect.width, 320),
      maxWidth: Math.min(480, window.innerWidth - rect.left - 12),
      zIndex: 9999,
    }
  }

  return (
    <>
      <div
        onMouseEnter={open}
        onMouseLeave={close}
        className={`cursor-default overflow-hidden ${className}`}
        style={{
          display: '-webkit-box',
          WebkitLineClamp: lines,
          WebkitBoxOrient: 'vertical',
        }}
      >
        {text}
      </div>

      {rect &&
        createPortal(
          <div
            style={popoverStyle()}
            className="bg-gray-900 text-gray-100 text-xs p-3 rounded-lg shadow-2xl select-text whitespace-pre-wrap break-all max-h-48 overflow-y-auto"
            onMouseEnter={keepOpen}
            onMouseLeave={close}
          >
            {text}
          </div>,
          document.body,
        )}
    </>
  )
}
