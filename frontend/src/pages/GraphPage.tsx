import { Link } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardContent, Button } from '../components'
import { ChevronLeft, GitBranch } from 'lucide-react'

export function GraphPage() {
  return (
    <div className="space-y-6 animate-in">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/repositories" className="btn-ghost">
            <ChevronLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-text-primary">Dependency Graph</h1>
            <p className="text-text-secondary mt-1">Explore code dependencies and relationships</p>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitBranch className="h-5 w-5" />
            Dependency Graph
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-16">
            <GitBranch className="h-12 w-12 text-text-muted mx-auto mb-4" />
            <h3 className="text-lg font-medium text-text-primary mb-2">Dependency graph not available</h3>
            <p className="text-text-secondary mb-6">
              Import/reference extraction and graph visualization are not yet implemented.
              This feature will show actual detected relationships between modules and files.
            </p>
            <Button variant="secondary" onClick={() => console.log('Coming soon')}>
              Learn More
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}