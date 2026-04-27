import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getAudiobooks, scanLibrary } from '@/api/library'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useToast } from '@/hooks/use-toast'
import { formatBytes, formatDuration } from '@/lib/utils'
import { RefreshCw, FolderSearch } from 'lucide-react'

export default function Library() {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const { data: audiobooks, isLoading, refetch } = useQuery({
    queryKey: ['library'],
    queryFn: getAudiobooks,
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Library</h2>
          <p className="text-muted-foreground">
            Your audiobook collection.
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

      {isLoading ? (
        <div className="text-muted-foreground">Loading library...</div>
      ) : audiobooks?.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <p>Your library is empty.</p>
          <p className="text-sm mt-2">
            Download audiobooks or scan your library folder to add content.
          </p>
        </div>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[35%]">Title</TableHead>
                <TableHead>Author</TableHead>
                <TableHead>Narrator</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Added</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {audiobooks?.map((audiobook) => (
                <TableRow key={audiobook.id}>
                  <TableCell className="font-medium">
                    {audiobook.title}
                  </TableCell>
                  <TableCell>{audiobook.author || '-'}</TableCell>
                  <TableCell>{audiobook.narrator || '-'}</TableCell>
                  <TableCell>{formatBytes(audiobook.size_bytes)}</TableCell>
                  <TableCell>
                    {formatDuration(audiobook.duration_seconds)}
                  </TableCell>
                  <TableCell>
                    {new Date(audiobook.added_at).toLocaleDateString()}
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
