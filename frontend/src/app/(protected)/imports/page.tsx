'use client';

import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Upload,
  FileText,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  Loader2,
  ChevronRight,
  Package,
  Trash2,
} from 'lucide-react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

import {
  uploadImportFile,
  generateImportPreview,
  confirmImport,
  cancelImport,
  getImportJobs,
  type ImportJob,
} from '@/lib/api';

type ImportPlatform = 'moxfield' | 'archidekt' | 'deckbox' | 'tcgplayer' | 'generic_csv';

const PLATFORMS: { value: ImportPlatform; label: string; description: string }[] = [
  { value: 'moxfield', label: 'Moxfield', description: 'Export from Moxfield collection' },
  { value: 'archidekt', label: 'Archidekt', description: 'Export from Archidekt collection' },
  { value: 'deckbox', label: 'Deckbox', description: 'Export from Deckbox inventory' },
  { value: 'tcgplayer', label: 'TCGPlayer', description: 'Export from TCGPlayer collection' },
  { value: 'generic_csv', label: 'Generic CSV', description: 'Any CSV with card names' },
];

const STATUS_CONFIGS: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  pending: { icon: <Clock className="h-4 w-4" />, label: 'Pending', color: 'bg-yellow-500' },
  previewing: { icon: <Loader2 className="h-4 w-4 animate-spin" />, label: 'Parsing', color: 'bg-blue-500' },
  preview_ready: { icon: <FileText className="h-4 w-4" />, label: 'Ready', color: 'bg-purple-500' },
  importing: { icon: <Loader2 className="h-4 w-4 animate-spin" />, label: 'Importing', color: 'bg-blue-500' },
  completed: { icon: <CheckCircle2 className="h-4 w-4" />, label: 'Completed', color: 'bg-green-500' },
  failed: { icon: <XCircle className="h-4 w-4" />, label: 'Failed', color: 'bg-red-500' },
  cancelled: { icon: <XCircle className="h-4 w-4" />, label: 'Cancelled', color: 'bg-gray-500' },
};

function formatFileSize(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || isNaN(bytes)) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString();
}

export default function ImportsPage() {
  const queryClient = useQueryClient();
  const [selectedPlatform, setSelectedPlatform] = useState<ImportPlatform>('moxfield');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [activeJob, setActiveJob] = useState<ImportJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch import history
  const { data: historyData, isLoading: isLoadingHistory } = useQuery({
    queryKey: ['import-jobs'],
    queryFn: () => getImportJobs({ limit: 10 }),
  });

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile) throw new Error('No file selected');
      return uploadImportFile(selectedFile, selectedPlatform);
    },
    onSuccess: (job) => {
      setActiveJob(job);
      setSelectedFile(null);
      setError(null);
      // Automatically generate preview
      previewMutation.mutate(job.id);
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  // Preview mutation
  const previewMutation = useMutation({
    mutationFn: generateImportPreview,
    onSuccess: (job) => {
      setActiveJob(job);
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  // Confirm mutation
  const confirmMutation = useMutation({
    mutationFn: (skipUnmatched: boolean) => confirmImport(activeJob!.id, skipUnmatched),
    onSuccess: (job) => {
      setActiveJob(job);
      queryClient.invalidateQueries({ queryKey: ['import-jobs'] });
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  // Cancel mutation
  const cancelMutation = useMutation({
    mutationFn: () => cancelImport(activeJob!.id),
    onSuccess: () => {
      setActiveJob(null);
      queryClient.invalidateQueries({ queryKey: ['import-jobs'] });
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.endsWith('.csv')) {
        setError('Only CSV files are supported');
        return;
      }
      setSelectedFile(file);
      setError(null);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) {
      if (!file.name.endsWith('.csv')) {
        setError('Only CSV files are supported');
        return;
      }
      setSelectedFile(file);
      setError(null);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  const isProcessing = uploadMutation.isPending || previewMutation.isPending || confirmMutation.isPending;

  // Render the current step based on activeJob state
  const renderWorkflow = () => {
    if (!activeJob) {
      // Step 1: Upload
      return (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="h-5 w-5" />
              Import Collection
            </CardTitle>
            <CardDescription>
              Upload a CSV export from your collection manager to import cards into your inventory.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label>Platform</Label>
              <Select value={selectedPlatform} onValueChange={(v) => setSelectedPlatform(v as ImportPlatform)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PLATFORMS.map((platform) => (
                    <SelectItem key={platform.value} value={platform.value}>
                      <div className="flex flex-col">
                        <span>{platform.label}</span>
                        <span className="text-xs text-muted-foreground">{platform.description}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div
              className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-primary transition-colors"
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onClick={() => document.getElementById('file-input')?.click()}
            >
              <input
                id="file-input"
                type="file"
                accept=".csv"
                className="hidden"
                onChange={handleFileChange}
              />
              <Upload className="h-10 w-10 mx-auto mb-4 text-muted-foreground" />
              {selectedFile ? (
                <div>
                  <p className="font-medium">{selectedFile.name}</p>
                  <p className="text-sm text-muted-foreground">{formatFileSize(selectedFile.size)}</p>
                </div>
              ) : (
                <div>
                  <p className="font-medium">Drop your CSV file here</p>
                  <p className="text-sm text-muted-foreground">or click to browse</p>
                </div>
              )}
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <Button
              className="w-full"
              disabled={!selectedFile || isProcessing}
              onClick={() => uploadMutation.mutate()}
            >
              {uploadMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="mr-2 h-4 w-4" />
                  Upload and Preview
                </>
              )}
            </Button>
          </CardContent>
        </Card>
      );
    }

    if (activeJob.status === 'previewing' || previewMutation.isPending) {
      // Loading preview
      return (
        <Card>
          <CardHeader>
            <CardTitle>Processing Import</CardTitle>
            <CardDescription>Parsing file and matching cards...</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
            <p className="text-center text-muted-foreground">
              This may take a moment for large collections...
            </p>
          </CardContent>
        </Card>
      );
    }

    if (activeJob.status === 'preview_ready') {
      // Step 2: Preview
      const preview = activeJob.preview_data;
      const matchRate = preview ? Math.round((preview.matched / preview.total) * 100) : 0;

      return (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Import Preview
            </CardTitle>
            <CardDescription>
              Review the matched cards before importing to your inventory.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Summary stats */}
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center p-4 bg-muted rounded-lg">
                <div className="text-2xl font-bold">{preview?.total || 0}</div>
                <div className="text-sm text-muted-foreground">Total Cards</div>
              </div>
              <div className="text-center p-4 bg-green-500/10 rounded-lg">
                <div className="text-2xl font-bold text-green-600">{preview?.matched || 0}</div>
                <div className="text-sm text-muted-foreground">Matched</div>
              </div>
              <div className="text-center p-4 bg-yellow-500/10 rounded-lg">
                <div className="text-2xl font-bold text-yellow-600">{preview?.unmatched || 0}</div>
                <div className="text-sm text-muted-foreground">Unmatched</div>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Match Rate</span>
                <span>{matchRate}%</span>
              </div>
              <Progress value={matchRate} />
            </div>

            {/* Preview table */}
            {preview && preview.items.length > 0 && (
              <div className="border rounded-lg">
                <ScrollArea className="h-[300px]">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Card Name</TableHead>
                        <TableHead>Set</TableHead>
                        <TableHead>Qty</TableHead>
                        <TableHead>Condition</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {preview.items.map((item, idx) => (
                        <TableRow key={idx}>
                          <TableCell className="font-medium">{item.card_name}</TableCell>
                          <TableCell>{item.set_code || item.set_name || '-'}</TableCell>
                          <TableCell>{item.quantity}</TableCell>
                          <TableCell>{item.condition}</TableCell>
                          <TableCell>
                            {item.matched_card_id ? (
                              <Badge variant="default" className="bg-green-500">
                                <CheckCircle2 className="h-3 w-3 mr-1" />
                                Matched
                              </Badge>
                            ) : (
                              <Badge variant="secondary" className="bg-yellow-500/20 text-yellow-700">
                                <AlertCircle className="h-3 w-3 mr-1" />
                                Not Found
                              </Badge>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </ScrollArea>
              </div>
            )}

            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="flex gap-4">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => cancelMutation.mutate()}
                disabled={isProcessing}
              >
                <XCircle className="mr-2 h-4 w-4" />
                Cancel
              </Button>
              <Button
                className="flex-1"
                onClick={() => confirmMutation.mutate(true)}
                disabled={isProcessing || (preview?.matched || 0) === 0}
              >
                {confirmMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Importing...
                  </>
                ) : (
                  <>
                    <Package className="mr-2 h-4 w-4" />
                    Import {preview?.matched || 0} Cards
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      );
    }

    if (activeJob.status === 'importing' || confirmMutation.isPending) {
      return (
        <Card>
          <CardHeader>
            <CardTitle>Importing Cards</CardTitle>
            <CardDescription>Adding cards to your inventory...</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
            <p className="text-center text-muted-foreground">
              Please wait while we add cards to your inventory...
            </p>
          </CardContent>
        </Card>
      );
    }

    if (activeJob.status === 'completed') {
      return (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-green-600">
              <CheckCircle2 className="h-5 w-5" />
              Import Complete
            </CardTitle>
            <CardDescription>
              Your cards have been added to your inventory.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center p-4 bg-green-500/10 rounded-lg">
                <div className="text-2xl font-bold text-green-600">{activeJob.imported_count}</div>
                <div className="text-sm text-muted-foreground">Imported</div>
              </div>
              <div className="text-center p-4 bg-yellow-500/10 rounded-lg">
                <div className="text-2xl font-bold text-yellow-600">{activeJob.skipped_count}</div>
                <div className="text-sm text-muted-foreground">Skipped</div>
              </div>
              <div className="text-center p-4 bg-red-500/10 rounded-lg">
                <div className="text-2xl font-bold text-red-600">{activeJob.error_count}</div>
                <div className="text-sm text-muted-foreground">Errors</div>
              </div>
            </div>

            <Button className="w-full" onClick={() => setActiveJob(null)}>
              <ChevronRight className="mr-2 h-4 w-4" />
              Import Another Collection
            </Button>
          </CardContent>
        </Card>
      );
    }

    if (activeJob.status === 'failed') {
      return (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-red-600">
              <XCircle className="h-5 w-5" />
              Import Failed
            </CardTitle>
            <CardDescription>
              Something went wrong during the import.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{activeJob.error_message || 'Unknown error occurred'}</AlertDescription>
            </Alert>

            <Button className="w-full" onClick={() => setActiveJob(null)}>
              <ChevronRight className="mr-2 h-4 w-4" />
              Try Again
            </Button>
          </CardContent>
        </Card>
      );
    }

    return null;
  };

  return (
    <div className="container mx-auto py-6 space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Import Collection</h1>
        <p className="text-muted-foreground">
          Import your card collection from popular platforms.
        </p>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        {/* Main workflow */}
        <div>{renderWorkflow()}</div>

        {/* Import History */}
        <Card>
          <CardHeader>
            <CardTitle>Import History</CardTitle>
            <CardDescription>Your recent import jobs</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoadingHistory ? (
              <div className="space-y-4">
                {[...Array(3)].map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : historyData?.items.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">
                No import history yet
              </p>
            ) : (
              <div className="space-y-4">
                {historyData?.items.map((job) => {
                  const statusConfig = STATUS_CONFIGS[job.status] || STATUS_CONFIGS.pending;
                  return (
                    <div
                      key={job.id}
                      className="flex items-center justify-between p-4 border rounded-lg"
                    >
                      <div className="flex items-center gap-4">
                        <div className={`p-2 rounded-full ${statusConfig.color} text-white`}>
                          {statusConfig.icon}
                        </div>
                        <div>
                          <p className="font-medium">{job.filename}</p>
                          <p className="text-sm text-muted-foreground">
                            {PLATFORMS.find((p) => p.value === job.platform)?.label || job.platform}
                            {' • '}
                            {formatDate(job.created_at)}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <Badge variant="outline">{statusConfig.label}</Badge>
                        {job.status === 'completed' && (
                          <p className="text-sm text-muted-foreground mt-1">
                            {job.imported_count} cards
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
