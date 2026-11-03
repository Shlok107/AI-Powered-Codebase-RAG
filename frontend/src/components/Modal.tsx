import { Fragment, ReactNode, useEffect } from 'react'
import { X } from 'lucide-react'
import { cn } from '../utils/cn'
import { Button } from './Button'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  description?: string
  children: ReactNode
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
  showCloseButton?: boolean
}

export function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  size = 'md',
  showCloseButton = true,
}: ModalProps) {
  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const sizes = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
    full: 'max-w-[90vw]',
  }

  return (
    <Fragment>
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 animate-in"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        className={cn(
          'fixed inset-0 z-50 flex items-center justify-center p-4 animate-in',
          'pointer-events-none'
        )}
      >
        <div
          className={cn(
            'w-full bg-surface border border-surface-border rounded-xl shadow-2xl',
            'pointer-events-auto animate-in',
            sizes[size]
          )}
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
          aria-describedby={description ? 'modal-description' : undefined}
        >
          <div className="flex items-start justify-between p-6 border-b border-surface-border">
            <div>
              <h2 id="modal-title" className="text-lg font-semibold text-text-primary">
                {title}
              </h2>
              {description && (
                <p id="modal-description" className="mt-1 text-sm text-text-secondary">
                  {description}
                </p>
              )}
            </div>
            {showCloseButton && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onClose}
                aria-label="Close modal"
                className="text-text-secondary hover:text-text-primary"
              >
                <X className="h-5 w-5" />
              </Button>
            )}
          </div>
          <div className="p-6">{children}</div>
        </div>
      </div>
    </Fragment>
  )
}
