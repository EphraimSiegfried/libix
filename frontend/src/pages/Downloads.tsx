import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getDownloads, deleteDownload, Download } from '@/api/downloads'
import { importDownload } from '@/api/library'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { useToast } from '@/hooks/use-toast'
import { formatBytes } from '@/lib/utils'
import { Trash2, RefreshCw, FolderInput } from 'lucide-react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'

function getStatusBadgeVariant(status: Download['status']) {
  switch (status) {
    case 'downloading':
      return 'default'
    case 'seeding':
      return 'success'
    case 'completed':
      return 'success'
    case 'failed':
      return 'destructive'
    case 'cancelled':
      return 'secondary'
    default:
      return 'outline'
  }
}

export default function Downloads() {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const { data: downloads, isLoading, refetch } = useQuery({
    queryKey: ['downloads'],
    queryFn: getDownloads,
    refetchInterval: 5000, // Refresh every 5 seconds
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteDownload(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['downloads'] })
      toast({
        title: 'Download removed',
        description: 'The download has been removed.',
      })
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: 'Failed to remove download',
        description: error instanceof Error ? error.message : 'Failed to remove download',
      })
    },
  })

  const importMutation = useMutation({
    mutationFn: (id: number) => importDownload(id),
    onSuccess: (audiobooks) => {
      queryClient.invalidateQueries({ queryKey: ['downloads'] })
      queryClient.invalidateQueries({ queryKey: ['audiobooks'] })
      const count = audiobooks.length
      toast({
        title: 'Imported to library',
        description: count === 1
          ? `"${audiobooks[0].title}" has been added to your library.`
          : `${count} audiobooks have been added to your library.`,
      })
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: 'Failed to import',
        description: error instanceof Error ? error.message : 'Failed to import download',
      })
    },
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Downloads</h2>
          <p className="text-muted-foreground">
            Manage your active and completed downloads.
          </p>
        </div>
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {isLoading ? (
        <div className="text-muted-foreground">Loading downloads...</div>
      ) : downloads?.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          No downloads yet. Search for audiobooks to get started.
        </div>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40%]">Title</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Progress</TableHead>
                <TableHead>Size</TableHead>
                <TableHead className="w-[100px]"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {downloads?.map((download) => (
                <TableRow key={download.id}>
                  <TableCell className="font-medium">
                    <div>
                      {download.title}
                      {download.indexer && (
                        <span className="ml-2 text-xs text-muted-foreground">
                          ({download.indexer})
                        </span>
                      )}
                    </div>
                    {download.error_message && (
                      <div className="text-xs text-destructive mt-1">
                        {download.error_message}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant={getStatusBadgeVariant(download.status)}>
                      {download.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Progress value={download.progress} className="w-24" />
                      <span className="text-sm">{download.progress}%</span>
                    </div>
                  </TableCell>
                  <TableCell>{formatBytes(download.size_bytes)}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      {download.status === 'seeding' && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => importMutation.mutate(download.id)}
                          disabled={importMutation.isPending}
                          title="Retry Import to Library"
                        >
                          <FolderInput className="h-4 w-4" />
                        </Button>
                      )}
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Remove download?</AlertDialogTitle>
                            <AlertDialogDescription>
                              This will remove the download from the queue. The
                              downloaded files will not be deleted.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => deleteMutation.mutate(download.id)}
                            >
                              Remove
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
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
