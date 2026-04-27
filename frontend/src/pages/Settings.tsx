import { useQuery, useMutation } from '@tanstack/react-query'
import { getSettings, testProwlarr, testTransmission } from '@/api/settings'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/hooks/use-toast'
import { Check, X, Loader2 } from 'lucide-react'

export default function Settings() {
  const { toast } = useToast()

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
  })

  const testProwlarrMutation = useMutation({
    mutationFn: testProwlarr,
    onSuccess: (result) => {
      toast({
        title: result.success ? 'Prowlarr Connected' : 'Prowlarr Connection Failed',
        description: result.message,
        variant: result.success ? 'default' : 'destructive',
      })
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: 'Test failed',
        description: error instanceof Error ? error.message : 'Connection test failed',
      })
    },
  })

  const testTransmissionMutation = useMutation({
    mutationFn: testTransmission,
    onSuccess: (result) => {
      toast({
        title: result.success ? 'Transmission Connected' : 'Transmission Connection Failed',
        description: result.message,
        variant: result.success ? 'default' : 'destructive',
      })
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: 'Test failed',
        description: error instanceof Error ? error.message : 'Connection test failed',
      })
    },
  })

  if (isLoading) {
    return <div className="text-muted-foreground">Loading settings...</div>
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Settings</h2>
        <p className="text-muted-foreground">
          View your configuration. Edit config.yaml to make changes.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Prowlarr</CardTitle>
            <CardDescription>Indexer management</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">URL</span>
                <span>{settings?.prowlarr.url}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">API Key</span>
                <Badge variant={settings?.prowlarr.has_api_key ? 'success' : 'destructive'}>
                  {settings?.prowlarr.has_api_key ? (
                    <><Check className="h-3 w-3 mr-1" /> Configured</>
                  ) : (
                    <><X className="h-3 w-3 mr-1" /> Not Set</>
                  )}
                </Badge>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Categories</span>
                <span>{settings?.prowlarr.categories.join(', ')}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Result Limit</span>
                <span>{settings?.prowlarr.limit}</span>
              </div>
            </div>
            <Button
              onClick={() => testProwlarrMutation.mutate()}
              disabled={testProwlarrMutation.isPending}
              className="w-full"
            >
              {testProwlarrMutation.isPending && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              Test Connection
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Transmission</CardTitle>
            <CardDescription>Download client</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">URL</span>
                <span>{settings?.transmission.url}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Username</span>
                <span>{settings?.transmission.username || '-'}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Password</span>
                <Badge variant={settings?.transmission.has_password ? 'success' : 'secondary'}>
                  {settings?.transmission.has_password ? (
                    <><Check className="h-3 w-3 mr-1" /> Set</>
                  ) : (
                    'Not Set'
                  )}
                </Badge>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Download Dir</span>
                <span className="text-right max-w-[200px] truncate">
                  {settings?.transmission.download_dir}
                </span>
              </div>
            </div>
            <Button
              onClick={() => testTransmissionMutation.mutate()}
              disabled={testTransmissionMutation.isPending}
              className="w-full"
            >
              {testTransmissionMutation.isPending && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              Test Connection
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Library</CardTitle>
            <CardDescription>Audiobook storage</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Path</span>
              <span>{settings?.library.path}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Server</CardTitle>
            <CardDescription>Application settings</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Port</span>
              <span>{settings?.server_port}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Database</span>
              <span className="text-right max-w-[200px] truncate">
                {settings?.database_path}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
