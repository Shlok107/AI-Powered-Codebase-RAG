import { HTMLAttributes } from 'react'
import { cn } from '../utils/cn'

interface Column<T> {
  key: string
  header: string
  render?: (row: T) => React.ReactNode
  className?: string
}

interface TableProps<T> extends HTMLAttributes<HTMLTableElement> {
  columns: Column<T>[]
  data: T[]
  keyExtractor: (row: T) => string
  rowClassName?: (row: T) => string
  emptyMessage?: string
  loading?: boolean
  onRowClick?: (row: T) => void
}

export function Table<T>({
  columns,
  data,
  keyExtractor,
  rowClassName,
  emptyMessage = 'No data available',
  loading = false,
  onRowClick,
  className,
  ...props
}: TableProps<T>) {
  return (
    <div className={cn('table-container', className)}>
      {loading ? (
        <div className="p-8 text-center text-text-muted">
          <div className="animate-pulse-soft">Loading...</div>
        </div>
      ) : data.length === 0 ? (
        <div className="p-8 text-center text-text-muted">{emptyMessage}</div>
      ) : (
        <table className={cn('table', className)} {...props}>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key} className={cn(column.className)}>
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr
                key={keyExtractor(row)}
                className={cn(rowClassName?.(row), onRowClick && 'cursor-pointer')}
                onClick={() => onRowClick?.(row)}
              >
                {columns.map((column) => (
                  <td key={column.key} className={cn(column.className)}>
                    {column.render ? column.render(row) : (row as Record<string, unknown>)[column.key] as React.ReactNode}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}