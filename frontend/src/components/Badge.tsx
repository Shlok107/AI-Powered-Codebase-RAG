import { HTMLAttributes, forwardRef } from 'react'
import { cn } from '../utils/cn'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'critical' | 'high' | 'medium' | 'low' | 'info' | 'success' | 'warning'
  size?: 'sm' | 'md'
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = 'default', size = 'md', children, ...props }, ref) => {
    const variants = {
      default: 'bg-surface-border text-text-secondary',
      critical: 'bg-red-500/20 text-red-400 border border-red-500/30',
      high: 'bg-orange-500/20 text-orange-400 border border-orange-500/30',
      medium: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
      low: 'bg-green-500/20 text-green-400 border border-green-500/30',
      info: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
      success: 'bg-green-500/20 text-green-400 border border-green-500/30',
      warning: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
    }

    const sizes = {
      sm: 'px-2 py-0.5 text-xs',
      md: 'px-2.5 py-0.5 text-xs',
    }

    return (
      <span
        ref={ref}
        className={cn(
          'inline-flex items-center font-medium rounded-full',
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