import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getAudiobooks,
  scanLibrary,
  searchAsinForAudiobook,
  setAudiobookAsin,
  refreshAudiobookMetadata,
  deleteAudiobook,
  Audiobook,
  AsinSearchResult,
} from '@/api/library'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { useToast } from '@/hooks/use-toast'
import { formatBytes, formatDuration } from '@/lib/utils'
import {
  RefreshCw,
  RefreshCcw,
  FolderSearch,
  BookOpen,
  User,
  Mic,
  Clock,
  HardDrive,
  Calendar,
  FolderOpen,
  Hash,
  Search,
  Loader2,
  CheckCircle,
  ExternalLink,
  Trash2,
  Globe,
  UserCircle,
  Languages,
} from 'lucide-react'

export default function Library() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [selectedAudiobook, setSelectedAudiobook] = useState<Audiobook | null>(null)
  const [showAsinSearch, setShowAsinSearch] = useState(false)
  const [asinResults, setAsinResults] = useState<AsinSearchResult[]>([])
  const [searchingAsin, setSearchingAsin] = useState(false)
  const [manualAsin, setManualAsin] = useState('')
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [deleteFiles, setDeleteFiles] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const { data: audiobooks, isLoading, refetch } = useQuery({
    queryKey: ['library'],
    queryFn: getAudiobooks,
  })

  // Filter audiobooks based on search query
  const filteredAudiobooks = audiobooks?.filter((book) => {
    if (!searchQuery.trim()) return true
    const query = searchQuery.toLowerCase()
    return (
      book.title.toLowerCase().includes(query) ||
      book.author?.toLowerCase().includes(query) ||
      book.narrator?.toLowerCase().includes(query) ||
      book.series_name?.toLowerCase().includes(query) ||
      book.description?.toLowerCase().includes(query)
    )
  })

  const scanMutation = useMutation({
    mutationFn: scanLibrary,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['library'] })
      toast({
        title: 'Library scanned',
        description: `Added ${data.added} new audiobook(s), skipped ${data.skipped} existing.`,
      })
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: 'Scan failed',
        description: error instanceof Error ? error.message : 'Failed to scan library',
      })
    },
  })

  const setAsinMutation = useMutation({
    mutationFn: ({ audiobookId, asin }: { audiobookId: number; asin: string }) =>
      setAudiobookAsin(audiobookId, asin),
    onSuccess: (updatedAudiobook) => {
      queryClient.invalidateQueries({ queryKey: ['library'] })
      setSelectedAudiobook(updatedAudiobook)
      setShowAsinSearch(false)
      setAsinResults([])
      setManualAsin('')
      toast({
        title: 'Metadata updated',
        description: 'Audiobook metadata has been updated from Audnexus.',
      })
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: 'Failed to set ASIN',
        description: error instanceof Error ? error.message : 'Failed to update metadata',
      })
    },
  })

  const refreshMetadataMutation = useMutation({
    mutationFn: (audiobookId: number) => refreshAudiobookMetadata(audiobookId),
    onSuccess: (updatedAudiobook) => {
      queryClient.invalidateQueries({ queryKey: ['library'] })
      setSelectedAudiobook(updatedAudiobook)
      toast({
        title: 'Metadata refreshed',
        description: 'Audiobook metadata has been refreshed.',
      })
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: 'Failed to refresh metadata',
        description: error instanceof Error ? error.message : 'Failed to refresh metadata',
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: ({ audiobookId, deleteFiles }: { audiobookId: number; deleteFiles: boolean }) =>
      deleteAudiobook(audiobookId, deleteFiles),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['library'] })
      setSelectedAudiobook(null)
      setShowDeleteDialog(false)
      setDeleteFiles(false)
      toast({
        title: 'Audiobook deleted',
        description: 'The audiobook has been removed from your library.',
      })
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: 'Failed to delete',
        description: error instanceof Error ? error.message : 'Failed to delete audiobook',
      })
    },
  })

  const handleSearchAsin = async () => {
    if (!selectedAudiobook) return

    setSearchingAsin(true)
    setAsinResults([])
    setShowAsinSearch(true)

    try {
      const results = await searchAsinForAudiobook(selectedAudiobook.id)
      setAsinResults(results)
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Search failed',
        description: error instanceof Error ? error.message : 'Failed to search for ASINs',
      })
    } finally {
      setSearchingAsin(false)
    }
  }

  const handleSelectAsin = (asin: string) => {
    if (!selectedAudiobook) return
    setAsinMutation.mutate({ audiobookId: selectedAudiobook.id, asin })
  }

  const getCoverUrl = (audiobook: Audiobook) => {
    if (audiobook.cover_image_url) {
      return `/api/covers/proxy?url=${encodeURIComponent(audiobook.cover_image_url)}`
    }
    return null
  }

  const getCoverUrlFromResult = (result: AsinSearchResult) => {
    if (result.cover_url) {
      return `/api/covers/proxy?url=${encodeURIComponent(result.cover_url)}`
    }
    return null
  }

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Library</h2>
            <p className="text-muted-foreground">
              Your audiobook collection. {audiobooks?.length || 0} audiobook{audiobooks?.length !== 1 ? 's' : ''}.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => scanMutation.mutate()}
              disabled={scanMutation.isPending}
            >
              <FolderSearch className="h-4 w-4 mr-2" />
              {scanMutation.isPending ? 'Scanning...' : 'Scan Library'}
            </Button>
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Search bar */}
        {audiobooks && audiobooks.length > 0 && (
          <div className="flex gap-2 items-center">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by title, author, narrator, series..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            {searchQuery && (
              <span className="text-sm text-muted-foreground">
                {filteredAudiobooks?.length} of {audiobooks.length} shown
              </span>
            )}
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="text-muted-foreground">Loading library...</div>
      ) : audiobooks?.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <BookOpen className="h-16 w-16 mx-auto mb-4 opacity-50" />
          <p>Your library is empty.</p>
          <p className="text-sm mt-2">
            Download audiobooks or scan your library folder to add content.
          </p>
        </div>
      ) : filteredAudiobooks?.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <Search className="h-16 w-16 mx-auto mb-4 opacity-50" />
          <p>No audiobooks match your search.</p>
          <p className="text-sm mt-2">
            Try a different search term.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4">
          {filteredAudiobooks?.map((audiobook) => {
            const coverUrl = getCoverUrl(audiobook)
            return (
              <Card
                key={audiobook.id}
                className="cursor-pointer hover:ring-2 hover:ring-primary transition-all overflow-hidden"
                onClick={() => setSelectedAudiobook(audiobook)}
              >
                <div className="aspect-[2/3] relative bg-muted">
                  {coverUrl ? (
                    <img
                      src={coverUrl}
                      alt={audiobook.title}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        e.currentTarget.style.display = 'none'
                        const fallback = e.currentTarget.nextElementSibling as HTMLElement
                        if (fallback) fallback.style.display = 'flex'
                      }}
                    />
                  ) : null}
                  <div
                    className={`absolute inset-0 flex items-center justify-center bg-gradient-to-br from-muted to-muted-foreground/20 ${coverUrl ? 'hidden' : ''}`}
                  >
                    <BookOpen className="h-16 w-16 text-muted-foreground/50" />
                  </div>
                  {/* Series badge overlay */}
                  {audiobook.series_name && (
                    <div className="absolute top-2 left-2">
                      <Badge variant="secondary" className="text-xs">
                        {audiobook.series_name}
                        {audiobook.series_position && ` #${audiobook.series_position}`}
                      </Badge>
                    </div>
                  )}
                  {/* Language badge overlay */}
                  {audiobook.language && (
                    <div className="absolute top-2 right-2">
                      <Badge variant="outline" className="text-xs bg-background/80">
                        {audiobook.language}
                      </Badge>
                    </div>
                  )}
                  {/* Metadata source indicator */}
                  {!audiobook.asin && !audiobook.open_library_key && (
                    <div className="absolute bottom-2 right-2">
                      <Badge variant="outline" className="text-xs bg-background/80">
                        No metadata
                      </Badge>
                    </div>
                  )}
                  {!audiobook.asin && audiobook.open_library_key && (
                    <div className="absolute bottom-2 right-2">
                      <Badge variant="secondary" className="text-xs bg-background/80">
                        OpenLibrary
                      </Badge>
                    </div>
                  )}
                </div>
                <CardHeader className="p-3 pb-1">
                  <CardTitle className="text-sm line-clamp-2 leading-tight">
                    {audiobook.title}
                  </CardTitle>
                  <CardDescription className="text-xs line-clamp-1">
                    {audiobook.author || 'Unknown Author'}
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-3 pt-0">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    {audiobook.duration_seconds && (
                      <span>{formatDuration(audiobook.duration_seconds)}</span>
                    )}
                    {audiobook.duration_seconds && audiobook.size_bytes && (
                      <span>-</span>
                    )}
                    {audiobook.size_bytes && (
                      <span>{formatBytes(audiobook.size_bytes)}</span>
                    )}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {/* Detail Dialog */}
      <Dialog open={!!selectedAudiobook && !showAsinSearch} onOpenChange={(open) => !open && setSelectedAudiobook(null)}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          {selectedAudiobook && (
            <>
              <DialogHeader>
                <DialogTitle className="text-xl">{selectedAudiobook.title}</DialogTitle>
                <DialogDescription>
                  {selectedAudiobook.author && `by ${selectedAudiobook.author}`}
                </DialogDescription>
              </DialogHeader>

              <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-6">
                {/* Cover Image */}
                <div className="aspect-[2/3] relative bg-muted rounded-lg overflow-hidden">
                  {getCoverUrl(selectedAudiobook) ? (
                    <img
                      src={getCoverUrl(selectedAudiobook)!}
                      alt={selectedAudiobook.title}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        e.currentTarget.style.display = 'none'
                      }}
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-muted to-muted-foreground/20">
                      <BookOpen className="h-20 w-20 text-muted-foreground/50" />
                    </div>
                  )}
                </div>

                {/* Metadata */}
                <div className="space-y-4">
                  {/* Quick info badges */}
                  <div className="flex flex-wrap gap-2">
                    {selectedAudiobook.series_name && (
                      <Badge variant="default">
                        {selectedAudiobook.series_name}
                        {selectedAudiobook.series_position && ` #${selectedAudiobook.series_position}`}
                      </Badge>
                    )}
                    {selectedAudiobook.asin && (
                      <Badge variant="outline">ASIN: {selectedAudiobook.asin}</Badge>
                    )}
                    {selectedAudiobook.open_library_key && (
                      <Badge variant="outline">
                        OpenLibrary: {selectedAudiobook.open_library_key.replace('/works/', '')}
                      </Badge>
                    )}
                    {!selectedAudiobook.asin && (
                      <Button variant="outline" size="sm" onClick={handleSearchAsin}>
                        <Search className="h-3 w-3 mr-1" />
                        Find ASIN
                      </Button>
                    )}
                  </div>

                  {/* Metadata grid */}
                  <div className="grid grid-cols-1 gap-3 text-sm">
                    {selectedAudiobook.author && (
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <span className="text-muted-foreground">Author:</span>
                        <span className="font-medium">{selectedAudiobook.author}</span>
                      </div>
                    )}

                    {selectedAudiobook.narrator && (
                      <div className="flex items-center gap-2">
                        <Mic className="h-4 w-4 text-muted-foreground" />
                        <span className="text-muted-foreground">Narrator:</span>
                        <span className="font-medium">{selectedAudiobook.narrator}</span>
                      </div>
                    )}

                    {selectedAudiobook.duration_seconds && (
                      <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4 text-muted-foreground" />
                        <span className="text-muted-foreground">Duration:</span>
                        <span className="font-medium">{formatDuration(selectedAudiobook.duration_seconds)}</span>
                      </div>
                    )}

                    {selectedAudiobook.size_bytes && (
                      <div className="flex items-center gap-2">
                        <HardDrive className="h-4 w-4 text-muted-foreground" />
                        <span className="text-muted-foreground">Size:</span>
                        <span className="font-medium">{formatBytes(selectedAudiobook.size_bytes)}</span>
                      </div>
                    )}

                    {selectedAudiobook.release_date && (
                      <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-muted-foreground" />
                        <span className="text-muted-foreground">Released:</span>
                        <span className="font-medium">
                          {new Date(selectedAudiobook.release_date).toLocaleDateString()}
                        </span>
                      </div>
                    )}

                    {selectedAudiobook.language && (
                      <div className="flex items-center gap-2">
                        <Languages className="h-4 w-4 text-muted-foreground" />
                        <span className="text-muted-foreground">Language:</span>
                        <span className="font-medium">{selectedAudiobook.language}</span>
                      </div>
                    )}

                    {selectedAudiobook.indexer && (
                      <div className="flex items-center gap-2">
                        <Globe className="h-4 w-4 text-muted-foreground" />
                        <span className="text-muted-foreground">Source:</span>
                        {selectedAudiobook.source_url ? (
                          <a
                            href={selectedAudiobook.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium text-primary hover:underline flex items-center gap-1"
                          >
                            {selectedAudiobook.indexer}
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        ) : (
                          <span className="font-medium">{selectedAudiobook.indexer}</span>
                        )}
                      </div>
                    )}

                    {selectedAudiobook.added_by && (
                      <div className="flex items-center gap-2">
                        <UserCircle className="h-4 w-4 text-muted-foreground" />
                        <span className="text-muted-foreground">Added by:</span>
                        <span className="font-medium">{selectedAudiobook.added_by.username}</span>
                      </div>
                    )}

                    <div className="flex items-center gap-2">
                      <Calendar className="h-4 w-4 text-muted-foreground" />
                      <span className="text-muted-foreground">Added:</span>
                      <span className="font-medium">
                        {new Date(selectedAudiobook.added_at).toLocaleDateString()}
                      </span>
                    </div>

                    <div className="flex items-start gap-2">
                      <FolderOpen className="h-4 w-4 text-muted-foreground mt-0.5" />
                      <span className="text-muted-foreground">Path:</span>
                      <span className="font-medium text-xs break-all">{selectedAudiobook.path}</span>
                    </div>

                    {selectedAudiobook.id && (
                      <div className="flex items-center gap-2">
                        <Hash className="h-4 w-4 text-muted-foreground" />
                        <span className="text-muted-foreground">ID:</span>
                        <span className="font-medium">{selectedAudiobook.id}</span>
                      </div>
                    )}
                  </div>

                  {/* Description */}
                  {selectedAudiobook.description && (
                    <div className="pt-2 border-t">
                      <h4 className="text-sm font-medium mb-2">Description</h4>
                      <div
                        className="text-sm text-muted-foreground leading-relaxed prose prose-sm dark:prose-invert max-w-none prose-p:my-2 prose-p:text-muted-foreground"
                        dangerouslySetInnerHTML={{ __html: selectedAudiobook.description }}
                      />
                    </div>
                  )}

                  {/* Actions */}
                  <div className="pt-2 border-t flex gap-2 flex-wrap">
                    {(selectedAudiobook.asin || selectedAudiobook.open_library_key) && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => refreshMetadataMutation.mutate(selectedAudiobook.id)}
                        disabled={refreshMetadataMutation.isPending}
                      >
                        {refreshMetadataMutation.isPending ? (
                          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                        ) : (
                          <RefreshCcw className="h-3 w-3 mr-1" />
                        )}
                        Refresh Metadata
                      </Button>
                    )}
                    {selectedAudiobook.asin && (
                      <Button variant="outline" size="sm" onClick={handleSearchAsin}>
                        <Search className="h-3 w-3 mr-1" />
                        Change ASIN
                      </Button>
                    )}
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => setShowDeleteDialog(true)}
                    >
                      <Trash2 className="h-3 w-3 mr-1" />
                      Delete
                    </Button>
                  </div>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* ASIN Search Dialog */}
      <Dialog open={showAsinSearch} onOpenChange={(open) => !open && setShowAsinSearch(false)}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Find ASIN for "{selectedAudiobook?.title}"</DialogTitle>
            <DialogDescription>
              Select the correct audiobook from Audible to fetch metadata.
            </DialogDescription>
          </DialogHeader>

          {/* Manual ASIN entry */}
          <div className="flex gap-2 mb-4">
            <Input
              placeholder="Enter ASIN manually (e.g., B002VA9SWS)"
              value={manualAsin}
              onChange={(e) => setManualAsin(e.target.value.toUpperCase())}
              className="font-mono"
            />
            <Button
              onClick={() => manualAsin && handleSelectAsin(manualAsin)}
              disabled={!manualAsin || manualAsin.length < 10 || setAsinMutation.isPending}
            >
              {setAsinMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                'Set'
              )}
            </Button>
          </div>

          <div className="text-xs text-muted-foreground mb-4">
            Find the ASIN on{' '}
            <a
              href={`https://www.audible.com/search?keywords=${encodeURIComponent(selectedAudiobook?.title || '')}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Audible <ExternalLink className="h-3 w-3 inline" />
            </a>
            {' '}(look for "B0..." in the URL)
          </div>

          {searchingAsin ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              <span className="ml-3 text-muted-foreground">Searching Audible...</span>
            </div>
          ) : asinResults.length === 0 ? (
            <div className="text-center py-4 text-muted-foreground">
              <p>No automatic results found. Enter ASIN manually above.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {asinResults.map((result) => (
                <div
                  key={result.asin}
                  className="flex gap-4 p-3 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors"
                  onClick={() => handleSelectAsin(result.asin)}
                >
                  {/* Cover */}
                  <div className="w-16 h-24 flex-shrink-0 bg-muted rounded overflow-hidden">
                    {getCoverUrlFromResult(result) ? (
                      <img
                        src={getCoverUrlFromResult(result)!}
                        alt={result.title || ''}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          e.currentTarget.style.display = 'none'
                        }}
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <BookOpen className="h-6 w-6 text-muted-foreground" />
                      </div>
                    )}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <h4 className="font-medium line-clamp-2">{result.title || result.asin}</h4>
                    {result.author && (
                      <p className="text-sm text-muted-foreground">by {result.author}</p>
                    )}
                    {result.narrator && (
                      <p className="text-sm text-muted-foreground">Narrated by {result.narrator}</p>
                    )}
                    <div className="flex flex-wrap gap-2 mt-1">
                      <Badge variant="outline" className="text-xs">
                        {result.asin}
                      </Badge>
                      {result.duration_seconds && (
                        <Badge variant="secondary" className="text-xs">
                          {formatDuration(result.duration_seconds)}
                        </Badge>
                      )}
                      {result.series_name && (
                        <Badge variant="secondary" className="text-xs">
                          {result.series_name}
                          {result.series_position && ` #${result.series_position}`}
                        </Badge>
                      )}
                    </div>
                  </div>

                  {/* Select button */}
                  <div className="flex items-center">
                    {setAsinMutation.isPending ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <CheckCircle className="h-5 w-5 text-muted-foreground" />
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Audiobook</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedAudiobook?.title}" from your library?
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="flex items-center space-x-2 py-4">
            <Checkbox
              id="delete-files"
              checked={deleteFiles}
              onCheckedChange={(checked) => setDeleteFiles(checked === true)}
            />
            <Label htmlFor="delete-files" className="text-sm">
              Also delete files from disk
            </Label>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setDeleteFiles(false)}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (selectedAudiobook) {
                  deleteMutation.mutate({
                    audiobookId: selectedAudiobook.id,
                    deleteFiles,
                  })
                }
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Trash2 className="h-4 w-4 mr-2" />
              )}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
