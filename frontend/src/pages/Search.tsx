import { useState, useEffect, useRef, useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  search,
  searchMetadata,
  searchTorrentsForAudiobook,
  getMagnetLink,
  SearchResult,
  MetadataSearchResult,
  TorrentAvailabilityResult,
  TorrentSearchRequest,
} from '@/api/search'
import { addDownload, getDownloads, DownloadCreate } from '@/api/downloads'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/hooks/use-toast'
import { formatBytes, formatDuration } from '@/lib/utils'
import {
  Search as SearchIcon,
  Download,
  Loader2,
  ArrowLeft,
  AlertCircle,
  BookOpen,
  CheckCircle,
  XCircle,
  Zap,
  Library,
} from 'lucide-react'

type SearchMode = 'metadata' | 'direct'
type SearchStage = 'initial' | 'searching' | 'metadata' | 'torrents'

// Check if a torrent title is a good match for an audiobook
function isTitleMatch(torrentTitle: string, bookTitle: string, bookAuthor?: string): boolean {
  // Normalize strings: lowercase, remove special chars, split into words
  const normalize = (s: string) =>
    s.toLowerCase()
      .replace(/[^\w\s]/g, ' ')
      .split(/\s+/)
      .filter((w) => w.length > 2) // Skip short words like "a", "the", "of"

  const torrentWords = new Set(normalize(torrentTitle))
  const bookWords = normalize(bookTitle)
  const authorWords = bookAuthor ? normalize(bookAuthor) : []

  // Count how many significant book title words appear in torrent title
  const matchingBookWords = bookWords.filter((w) => torrentWords.has(w))
  const matchingAuthorWords = authorWords.filter((w) => torrentWords.has(w))

  // Require at least 60% of book title words to match
  const titleMatchRatio = bookWords.length > 0 ? matchingBookWords.length / bookWords.length : 0

  // If author is provided, require at least one author word to match
  const authorMatches = authorWords.length === 0 || matchingAuthorWords.length > 0

  return titleMatchRatio >= 0.6 && authorMatches
}

export default function Search() {
  const [query, setQuery] = useState('')
  const [searchMode, setSearchMode] = useState<SearchMode>('direct')
  const [stage, setStage] = useState<SearchStage>('initial')
  const [metadataResults, setMetadataResults] = useState<MetadataSearchResult[]>([])
  const [torrentResults, setTorrentResults] = useState<SearchResult[]>([])
  const [selectedBook, setSelectedBook] = useState<MetadataSearchResult | null>(null)
  const [availability, setAvailability] = useState<Map<string, TorrentAvailabilityResult>>(new Map())
  const [availabilityProgress, setAvailabilityProgress] = useState({ current: 0, total: 0 })
  const [checkingAvailability, setCheckingAvailability] = useState(false)
  const [hideUnavailable, setHideUnavailable] = useState(false)
  const [downloadedGuids, setDownloadedGuids] = useState<Set<string>>(new Set())
  const [selectedIndexers, setSelectedIndexers] = useState<Set<string>>(new Set())
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const abortControllerRef = useRef<AbortController | null>(null)

  // Fetch existing downloads to track status
  const { data: downloads } = useQuery({
    queryKey: ['downloads'],
    queryFn: getDownloads,
    refetchInterval: 3000, // Poll every 3 seconds for status updates
  })

  // Helper to get download status for a torrent
  const getDownloadStatus = useCallback((result: SearchResult): 'none' | 'downloading' | 'completed' | 'in_library' => {
    if (!downloads) return downloadedGuids.has(result.guid) ? 'downloading' : 'none'

    // Match by title (since guid isn't stored in downloads)
    const matchingDownload = downloads.find(d =>
      d.title === result.title ||
      downloadedGuids.has(result.guid)
    )

    if (!matchingDownload) return 'none'

    if (matchingDownload.audiobook_id) return 'in_library'
    if (matchingDownload.status === 'completed' || matchingDownload.status === 'seeding') return 'completed'
    if (matchingDownload.status === 'downloading' || matchingDownload.status === 'pending') return 'downloading'

    return 'none'
  }, [downloads, downloadedGuids])

  const metadataSearchMutation = useMutation({
    mutationFn: (q: string) => searchMetadata(q),
    onMutate: () => {
      setStage('searching')
    },
    onSuccess: (data) => {
      setMetadataResults(data.results)
      setStage('metadata')
      setSelectedBook(null)
      setTorrentResults([])
      setAvailability(new Map())
      setAvailabilityProgress({ current: 0, total: 0 })
      if (data.results.length === 0) {
        toast({
          title: 'No results',
          description: 'No audiobooks found matching your search.',
        })
      }
    },
    onError: (error) => {
      setStage('initial')
      toast({
        variant: 'destructive',
        title: 'Search failed',
        description: error instanceof Error ? error.message : 'Search failed',
      })
    },
  })

  const directSearchMutation = useMutation({
    mutationFn: (q: string) => search(q),
    onMutate: () => {
      setStage('searching')
    },
    onSuccess: (data) => {
      setTorrentResults(data)
      setStage('torrents')
      setSelectedBook(null)
      setMetadataResults([])
      if (data.length === 0) {
        toast({
          title: 'No results',
          description: 'No torrents found matching your search.',
        })
      }
    },
    onError: (error) => {
      setStage('initial')
      toast({
        variant: 'destructive',
        title: 'Search failed',
        description: error instanceof Error ? error.message : 'Search failed',
      })
    },
  })

  // Check availability after metadata search completes - one by one for progress
  useEffect(() => {
    if (metadataResults.length > 0 && availability.size === 0 && !checkingAvailability) {
      setCheckingAvailability(true)
      setAvailabilityProgress({ current: 0, total: metadataResults.length })

      // Create abort controller for cancellation
      abortControllerRef.current = new AbortController()

      const checkAvailabilitySequentially = async () => {
        const newAvailability = new Map<string, TorrentAvailabilityResult>()

        for (let i = 0; i < metadataResults.length; i++) {
          // Check if aborted
          if (abortControllerRef.current?.signal.aborted) {
            break
          }

          const book = metadataResults[i]
          const request: TorrentSearchRequest = {
            title: book.title,
            author: book.author || undefined,
            asin: book.asin || undefined,  // Only pass if it's a real ASIN
          }

          try {
            const results = await searchTorrentsForAudiobook(request)
            // Filter results to only count those that actually match this audiobook
            const matchingResults = results.filter((r) =>
              isTitleMatch(r.title, book.title, book.author || undefined)
            )
            const key = book.asin || book.open_library_key || book.title
            const result: TorrentAvailabilityResult = {
              asin: book.asin,
              title: book.title,
              available: matchingResults.length > 0,
              count: matchingResults.length,
            }
            newAvailability.set(key, result)

            // Update state incrementally
            setAvailability(new Map(newAvailability))
            setAvailabilityProgress({ current: i + 1, total: metadataResults.length })
          } catch {
            // Mark as unavailable on error
            const key = book.asin || book.open_library_key || book.title
            newAvailability.set(key, {
              asin: book.asin,
              title: book.title,
              available: false,
              count: 0,
            })
            setAvailability(new Map(newAvailability))
            setAvailabilityProgress({ current: i + 1, total: metadataResults.length })
          }
        }

        setCheckingAvailability(false)
      }

      checkAvailabilitySequentially()
    }

    // Cleanup on unmount or when results change
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [metadataResults, availability.size, checkingAvailability])

  const torrentSearchMutation = useMutation({
    mutationFn: searchTorrentsForAudiobook,
    onSuccess: (data) => {
      setTorrentResults(data)
      setStage('torrents')
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: 'Torrent search failed',
        description: error instanceof Error ? error.message : 'Failed to search torrents',
      })
    },
  })

  const downloadMutation = useMutation({
    mutationFn: ({ data, guid }: { data: DownloadCreate; guid: string }) => {
      // Optimistically mark as downloading
      setDownloadedGuids(prev => new Set([...prev, guid]))
      return addDownload(data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['downloads'] })
      toast({
        title: 'Download added',
        description: 'The download has been added to the queue.',
      })
    },
    onError: (error, { guid }) => {
      // Remove from downloaded set on error
      setDownloadedGuids(prev => {
        const next = new Set(prev)
        next.delete(guid)
        return next
      })
      toast({
        variant: 'destructive',
        title: 'Failed to add download',
        description: error instanceof Error ? error.message : 'Failed to add download',
      })
    },
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    // Cancel any ongoing availability check
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    setCheckingAvailability(false)
    setAvailability(new Map())
    setSelectedIndexers(new Set()) // Clear indexer filter

    if (query.trim()) {
      if (searchMode === 'metadata') {
        metadataSearchMutation.mutate(query)
      } else {
        directSearchMutation.mutate(query)
      }
    }
  }

  const handleFindDownloads = (book: MetadataSearchResult) => {
    setSelectedBook(book)
    setSelectedIndexers(new Set()) // Clear indexer filter
    torrentSearchMutation.mutate({
      title: book.title,
      author: book.author || undefined,
      asin: book.asin || undefined,
    })
  }

  const handleDownload = async (result: SearchResult) => {
    let magnetUrl = result.magnet_url

    // If no magnet or download URL, try to fetch it (for AudioBookBay)
    if (!magnetUrl && !result.download_url && result.info_url) {
      try {
        // Optimistically mark as downloading
        setDownloadedGuids(prev => new Set([...prev, result.guid]))
        magnetUrl = await getMagnetLink(result.info_url)
        if (!magnetUrl) {
          setDownloadedGuids(prev => {
            const next = new Set(prev)
            next.delete(result.guid)
            return next
          })
          toast({
            variant: 'destructive',
            title: 'Failed to get magnet link',
            description: 'Could not retrieve the magnet link from AudioBookBay.',
          })
          return
        }
      } catch (error) {
        setDownloadedGuids(prev => {
          const next = new Set(prev)
          next.delete(result.guid)
          return next
        })
        toast({
          variant: 'destructive',
          title: 'Failed to get magnet link',
          description: error instanceof Error ? error.message : 'Failed to fetch magnet link',
        })
        return
      }
    }

    const downloadData: DownloadCreate = {
      title: result.title,
      download_url: result.download_url || undefined,
      magnet_url: magnetUrl || undefined,
      info_url: result.info_url || undefined,
      indexer: result.indexer,
      size: result.size,
      // Include metadata if we have a selected book (from metadata search flow)
      metadata_asin: selectedBook?.asin || undefined,
      metadata_open_library_key: selectedBook?.open_library_key || undefined,
      metadata_author: selectedBook?.author || undefined,
      metadata_narrator: selectedBook?.narrator || undefined,
      metadata_description: selectedBook?.description || undefined,
      metadata_duration_seconds: selectedBook?.duration_seconds || undefined,
      metadata_cover_url: selectedBook?.cover_url || undefined,
      metadata_series_name: selectedBook?.series_name || undefined,
      metadata_series_position: selectedBook?.series_position || undefined,
      metadata_language: selectedBook?.language || undefined,
    }
    downloadMutation.mutate({ data: downloadData, guid: result.guid })
  }

  const handleBack = () => {
    if (searchMode === 'metadata' && metadataResults.length > 0) {
      setStage('metadata')
      setSelectedBook(null)
      setTorrentResults([])
    } else {
      setStage('initial')
      setTorrentResults([])
      setMetadataResults([])
    }
  }

  const getCoverProxyUrl = (url: string) => {
    return `/api/covers/proxy?url=${encodeURIComponent(url)}`
  }

  const getAvailability = (book: MetadataSearchResult): TorrentAvailabilityResult | undefined => {
    // Use ASIN, OpenLibrary key, or title as lookup key
    const key = book.asin || book.open_library_key || book.title
    return availability.get(key)
  }

  // Filter results based on availability
  const filteredResults = hideUnavailable
    ? metadataResults.filter((book) => {
        const avail = getAvailability(book)
        return avail?.available !== false
      })
    : metadataResults

  const unavailableCount = metadataResults.filter((book) => {
    const avail = getAvailability(book)
    return avail?.available === false
  }).length

  const isSearching = metadataSearchMutation.isPending || directSearchMutation.isPending

  // Get unique indexers from torrent results
  const availableIndexers = [...new Set(torrentResults.map((r) => r.indexer))].sort()

  // Filter torrent results by selected indexers
  const filteredTorrentResults = selectedIndexers.size === 0
    ? torrentResults
    : torrentResults.filter((r) => selectedIndexers.has(r.indexer))

  const toggleIndexer = (indexer: string) => {
    setSelectedIndexers((prev) => {
      const next = new Set(prev)
      if (next.has(indexer)) {
        next.delete(indexer)
      } else {
        next.add(indexer)
      }
      return next
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Search</h2>
        <p className="text-muted-foreground">
          Search for audiobooks and find available downloads.
        </p>
      </div>

      <div className="space-y-4">
        {/* Search mode toggle */}
        <div className="flex gap-2">
          <Button
            variant={searchMode === 'direct' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setSearchMode('direct')}
          >
            <Zap className="h-4 w-4 mr-2" />
            Direct Search
          </Button>
          <Button
            variant={searchMode === 'metadata' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setSearchMode('metadata')}
          >
            <Library className="h-4 w-4 mr-2" />
            With Metadata
          </Button>
        </div>

        <form onSubmit={handleSearch} className="flex gap-2">
          <Input
            placeholder={searchMode === 'direct' ? 'Search torrents directly...' : 'Search for audiobooks...'}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="max-w-md"
          />
          <Button type="submit" disabled={isSearching}>
            {isSearching ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <SearchIcon className="h-4 w-4" />
            )}
            <span className="ml-2">Search</span>
          </Button>
        </form>

        {searchMode === 'direct' && stage === 'initial' && (
          <p className="text-sm text-muted-foreground">
            Search torrents directly by title, author, or any keywords. Faster but without metadata enrichment.
          </p>
        )}
        {searchMode === 'metadata' && stage === 'initial' && (
          <p className="text-sm text-muted-foreground">
            Search audiobook metadata first, then find torrents. Slower but includes cover images, narrators, and series info.
          </p>
        )}
      </div>

      {/* Searching progress */}
      {stage === 'searching' && (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <span className="text-sm font-medium">
              {searchMode === 'metadata' ? 'Searching audiobook metadata...' : 'Searching torrents...'}
            </span>
          </div>
          <Progress value={undefined} className="h-2" />
        </div>
      )}

      {stage === 'metadata' && metadataResults.length > 0 && (
        <>
          {/* Availability progress bar */}
          {checkingAvailability && availabilityProgress.total > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Checking torrent availability...</span>
                </div>
                <span className="text-muted-foreground">
                  {availabilityProgress.current} / {availabilityProgress.total}
                </span>
              </div>
              <Progress
                value={(availabilityProgress.current / availabilityProgress.total) * 100}
                className="h-2"
              />
            </div>
          )}

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              {!checkingAvailability && availability.size > 0 && (
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="hide-unavailable"
                    checked={hideUnavailable}
                    onCheckedChange={(checked: boolean | 'indeterminate') => setHideUnavailable(checked === true)}
                  />
                  <Label htmlFor="hide-unavailable" className="text-sm cursor-pointer">
                    Hide unavailable ({unavailableCount})
                  </Label>
                </div>
              )}
            </div>
            <div className="text-sm text-muted-foreground">
              {filteredResults.length} of {metadataResults.length} results
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filteredResults.map((book) => {
              const avail = getAvailability(book)
              const isUnavailable = avail?.available === false
              const torrentCount = avail?.count || 0

              return (
                <Card
                  key={book.asin || book.open_library_key || book.title}
                  className={`flex flex-col ${isUnavailable ? 'opacity-60' : ''}`}
                >
                  <CardHeader className="pb-2">
                    <div className="relative">
                      {book.cover_url ? (
                        <img
                          src={getCoverProxyUrl(book.cover_url)}
                          alt={book.title}
                          className="w-full h-48 object-cover rounded-md mb-2"
                          onError={(e) => {
                            e.currentTarget.style.display = 'none'
                          }}
                        />
                      ) : (
                        <div className="w-full h-48 bg-muted rounded-md mb-2 flex items-center justify-center">
                          <BookOpen className="h-12 w-12 text-muted-foreground" />
                        </div>
                      )}
                      {/* Availability badge */}
                      {avail && (
                        <div className="absolute top-2 right-2">
                          {avail.available ? (
                            <Badge variant="default" className="bg-green-600">
                              <CheckCircle className="h-3 w-3 mr-1" />
                              {torrentCount}
                            </Badge>
                          ) : (
                            <Badge variant="destructive">
                              <XCircle className="h-3 w-3 mr-1" />
                              None
                            </Badge>
                          )}
                        </div>
                      )}
                      {/* Loading indicator while checking this specific book */}
                      {!avail && checkingAvailability && (
                        <div className="absolute top-2 right-2">
                          <Badge variant="secondary">
                            <Loader2 className="h-3 w-3 animate-spin" />
                          </Badge>
                        </div>
                      )}
                    </div>
                    <CardTitle className="line-clamp-2 text-base">{book.title}</CardTitle>
                    <CardDescription className="line-clamp-1">
                      {book.author || 'Unknown Author'}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="flex-1 pb-2">
                    <div className="text-sm text-muted-foreground space-y-1">
                      {book.narrator && (
                        <p className="line-clamp-1">Narrated by {book.narrator}</p>
                      )}
                      {book.duration_seconds && (
                        <p>{formatDuration(book.duration_seconds)}</p>
                      )}
                      {book.series_name && (
                        <Badge variant="outline" className="mt-1">
                          {book.series_name}
                          {book.series_position && ` #${book.series_position}`}
                        </Badge>
                      )}
                    </div>
                  </CardContent>
                  <CardFooter>
                    <Button
                      className="w-full"
                      variant={isUnavailable ? 'secondary' : 'default'}
                      onClick={() => handleFindDownloads(book)}
                      disabled={torrentSearchMutation.isPending}
                    >
                      {torrentSearchMutation.isPending && selectedBook?.asin === book.asin ? (
                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      ) : (
                        <SearchIcon className="h-4 w-4 mr-2" />
                      )}
                      {isUnavailable ? 'No Downloads' : 'Find Downloads'}
                    </Button>
                  </CardFooter>
                </Card>
              )
            })}
          </div>
        </>
      )}

      {stage === 'torrents' && (
        <div className="space-y-4">
          {/* Header with back button and selected book info (if from metadata search) */}
          <div className="flex items-start gap-4 p-4 bg-muted rounded-lg">
            <Button variant="ghost" size="icon" onClick={handleBack}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
            {selectedBook ? (
              <>
                {selectedBook.cover_url && (
                  <img
                    src={getCoverProxyUrl(selectedBook.cover_url)}
                    alt={selectedBook.title}
                    className="w-16 h-24 object-cover rounded"
                    onError={(e) => {
                      e.currentTarget.style.display = 'none'
                    }}
                  />
                )}
                <div className="flex-1">
                  <h3 className="font-semibold text-lg">{selectedBook.title}</h3>
                  <p className="text-muted-foreground">
                    {selectedBook.author}
                    {selectedBook.narrator && ` - ${selectedBook.narrator}`}
                  </p>
                  <div className="flex gap-2 mt-1">
                    {selectedBook.duration_seconds && (
                      <Badge variant="secondary">
                        {formatDuration(selectedBook.duration_seconds)}
                      </Badge>
                    )}
                    {selectedBook.series_name && (
                      <Badge variant="outline">
                        {selectedBook.series_name}
                        {selectedBook.series_position && ` #${selectedBook.series_position}`}
                      </Badge>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="flex-1">
                <h3 className="font-semibold text-lg">Search Results</h3>
                <p className="text-muted-foreground">
                  {selectedIndexers.size > 0
                    ? `${filteredTorrentResults.length} of ${torrentResults.length} torrent${torrentResults.length !== 1 ? 's' : ''}`
                    : `${torrentResults.length} torrent${torrentResults.length !== 1 ? 's' : ''}`
                  } found for "{query}"
                </p>
              </div>
            )}
          </div>

          {/* Indexer filter */}
          {availableIndexers.length > 1 && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm text-muted-foreground">Filter by indexer:</span>
              {availableIndexers.map((indexer) => (
                <Button
                  key={indexer}
                  variant={selectedIndexers.has(indexer) ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => toggleIndexer(indexer)}
                  className="h-7"
                >
                  {indexer}
                  <Badge variant="secondary" className="ml-1.5 h-4 px-1 text-xs">
                    {torrentResults.filter((r) => r.indexer === indexer).length}
                  </Badge>
                </Button>
              ))}
              {selectedIndexers.size > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedIndexers(new Set())}
                  className="h-7 text-muted-foreground"
                >
                  Clear
                </Button>
              )}
            </div>
          )}

          {filteredTorrentResults.length === 0 && torrentResults.length > 0 ? (
            <div className="flex items-center gap-2 p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
              <AlertCircle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
              <span className="text-yellow-800 dark:text-yellow-200">
                No torrents match the selected filters.
              </span>
            </div>
          ) : filteredTorrentResults.length === 0 ? (
            <div className="flex items-center gap-2 p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
              <AlertCircle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
              <span className="text-yellow-800 dark:text-yellow-200">
                No torrents found{selectedBook ? ' for this audiobook' : ''}.
              </span>
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[50%]">Release</TableHead>
                    <TableHead>Indexer</TableHead>
                    <TableHead>Size</TableHead>
                    <TableHead>S/L</TableHead>
                    <TableHead className="w-[80px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredTorrentResults.map((result) => (
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
                        {result.seeders === 0 && result.leechers === 0 ? (
                          <span className="text-muted-foreground">-</span>
                        ) : (
                          <>
                            <span className="text-green-600">{result.seeders}</span>
                            {' / '}
                            <span className="text-red-600">{result.leechers}</span>
                          </>
                        )}
                      </TableCell>
                      <TableCell>
                        {(() => {
                          const status = getDownloadStatus(result)
                          if (status === 'in_library') {
                            return (
                              <Button size="sm" variant="ghost" disabled className="text-green-600">
                                <Library className="h-4 w-4" />
                              </Button>
                            )
                          }
                          if (status === 'completed') {
                            return (
                              <Button size="sm" variant="ghost" disabled className="text-green-600">
                                <CheckCircle className="h-4 w-4" />
                              </Button>
                            )
                          }
                          if (status === 'downloading') {
                            return (
                              <Button size="sm" variant="ghost" disabled className="text-blue-600">
                                <Loader2 className="h-4 w-4 animate-spin" />
                              </Button>
                            )
                          }
                          return (
                            <Button
                              size="sm"
                              onClick={() => handleDownload(result)}
                              disabled={!result.download_url && !result.magnet_url}
                            >
                              <Download className="h-4 w-4" />
                            </Button>
                          )
                        })()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
