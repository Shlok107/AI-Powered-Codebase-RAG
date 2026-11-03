import { HTMLAttributes, forwardRef } from 'react'
import { cn } from '../utils/cn'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'critical' | 'high' | 'medium' | 'low' | 'info' | 'success' | 'warning' | 'pending' | 'processing' | 'indexed' | 'failed' | 'open' | 'dismissed' | 'resolved'
  size?: 'sm' | 'md'
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = 'default', size = 'md', children, ...props }, ref) => {
    const variants = {
      default: 'bg-surface-hover text-text-secondary',
      critical: 'bg-status-danger/15 text-status-danger',
      high: 'bg-status-danger/15 text-status-danger',
      medium: 'bg-status-warning/15 text-status-warning',
      low: 'bg-status-cyan/15 text-status-cyan',
      info: 'bg-surface-hover text-text-secondary',
      success: 'bg-status-success/15 text-status-success',
      warning: 'bg-status-warning/15 text-status-warning',
      pending: 'bg-surface-hover text-text-secondary',
      processing: 'bg-status-cyan/15 text-status-cyan',
      indexed: 'bg-status-success/15 text-status-success',
      failed: 'bg-status-danger/15 text-status-danger',
      open: 'bg-status-warning/15 text-status-warning',
      dismissed: 'bg-surface-hover text-text-muted',
      resolved: 'bg-status-success/15 text-status-success',
    }

    const sizes = {
      sm: 'px-2 py-0.5 text-xs',
      md: 'px-2.5 py-0.5 text-xs',
    }

    return (
      <span
        ref={ref}
        className={cn(
          'inline-flex items-center font-medium rounded',
          variants[variant],
          sizes[size],
          className
        )}
        {...props}
      >
        {children}
      </span>
    )
  }
)

Badge.displayName = 'Badge'
