import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { search, SearchResult } from '@/api/search'
import { addDownload } from '@/api/downloads'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/hooks/use-toast'
import { formatBytes } from '@/lib/utils'
import { Search as SearchIcon, Download, Loader2 } from 'lucide-react'

export default function Search() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const { toast } = useToast()

  const searchMutation = useMutation({
    mutationFn: search,
    onSuccess: (data) => {
      setResults(data)
      if (data.length === 0) {
        toast({
          title: 'No results',
          description: 'No audiobooks found matching your search.',
        })
      }
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: 'Search failed',
        description: error instanceof Error ? error.message : 'Search failed',
      })
    },
  })

  const downloadMutation = useMutation({
    mutationFn: addDownload,
    onSuccess: () => {
      toast({
        title: 'Download added',
        description: 'The download has been added to the queue.',
      })
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: 'Failed to add download',
        description: error instanceof Error ? error.message : 'Failed to add download',
      })
    },
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      searchMutation.mutate(query)
    }
  }

  const handleDownload = (result: SearchResult) => {
    downloadMutation.mutate({
      title: result.title,
      download_url: result.download_url || undefined,
      magnet_url: result.magnet_url || undefined,
      indexer: result.indexer,
      size: result.size,
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Search</h2>
        <p className="text-muted-foreground">
          Search for audiobooks across your configured indexers.
        </p>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2">
        <Input
          placeholder="Search for audiobooks..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="max-w-md"
        />
        <Button type="submit" disabled={searchMutation.isPending}>
          {searchMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <SearchIcon className="h-4 w-4" />
          )}
          <span className="ml-2">Search</span>
        </Button>
      </form>

      {results.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[50%]">Title</TableHead>
                <TableHead>Indexer</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>Seeders</TableHead>
                <TableHead className="w-[100px]"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {results.map((result) => (
                <TableRow key={result.guid}>
                  <TableCell className="font-medium">
                    {result.info_url ? (
                      <a
                        href={result.info_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:underline"
                      >
                        {result.title}
                      </a>
                    ) : (
                      result.title
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{result.indexer}</Badge>
                  </TableCell>
                  <TableCell>{formatBytes(result.size)}</TableCell>
                  <TableCell>
                    <span className="text-green-600">{result.seeders}</span>
                    {' / '}
                    <span className="text-red-600">{result.leechers}</span>
                  </TableCell>
                  <TableCell>
                    <Button
                      size="sm"
                      onClick={() => handleDownload(result)}
                      disabled={
                        downloadMutation.isPending ||
                        (!result.download_url && !result.magnet_url)
                      }
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
