'use client';

import { useState } from 'react';
import { X, Upload, FileText, AlertCircle, CheckCircle2 } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { importInventory } from '@/lib/api';
import type { InventoryImportResponse, InventoryCondition } from '@/types';

interface InventoryImportModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const CONDITION_OPTIONS: { value: InventoryCondition; label: string }[] = [
  { value: 'MINT', label: 'Mint' },
  { value: 'NEAR_MINT', label: 'Near Mint' },
  { value: 'LIGHTLY_PLAYED', label: 'Lightly Played' },
  { value: 'MODERATELY_PLAYED', label: 'Moderately Played' },
  { value: 'HEAVILY_PLAYED', label: 'Heavily Played' },
  { value: 'DAMAGED', label: 'Damaged' },
];

export function InventoryImportModal({ isOpen, onClose }: InventoryImportModalProps) {
  const [content, setContent] = useState('');
  const [format, setFormat] = useState<'auto' | 'csv' | 'plaintext'>('auto');
  const [defaultCondition, setDefaultCondition] = useState<InventoryCondition>('NEAR_MINT');
  const [acquisitionSource, setAcquisitionSource] = useState('');
  const [result, setResult] = useState<InventoryImportResponse | null>(null);
  
  const queryClient = useQueryClient();
  
  const importMutation = useMutation({
    mutationFn: () => importInventory(content, {
      format,
      defaultCondition,
      defaultAcquisitionSource: acquisitionSource || undefined,
    }),
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
      queryClient.invalidateQueries({ queryKey: ['inventory-analytics'] });
    },
  });
  
  const handleClose = () => {
    setContent('');
    setResult(null);
    onClose();
  };
  
  if (!isOpen) return null;
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <Card className="w-full max-w-3xl max-h-[90vh] overflow-hidden bg-[rgb(var(--card))] border-[rgb(var(--border))]">
        <div className="flex items-center justify-between p-4 border-b border-[rgb(var(--border))]">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-gradient-to-br from-amber-500 to-orange-600">
              <Upload className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-[rgb(var(--foreground))]">Import Inventory</h2>
              <p className="text-sm text-[rgb(var(--muted-foreground))]">
                Import cards from CSV or plaintext
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-2 rounded-lg hover:bg-[rgb(var(--secondary))] transition-colors"
          >
            <X className="w-5 h-5 text-[rgb(var(--muted-foreground))]" />
          </button>
        </div>
        
        <CardContent className="p-4 overflow-y-auto max-h-[calc(90vh-120px)]">
          {!result ? (
            <div className="space-y-4">
              {/* Format Selection */}
              <div>
                <label className="block text-sm font-medium text-[rgb(var(--foreground))] mb-2">
                  Format
                </label>
                <div className="flex gap-2">
                  {(['auto', 'csv', 'plaintext'] as const).map((f) => (
                    <button
                      key={f}
                      onClick={() => setFormat(f)}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                        format === f
                          ? 'bg-amber-500/20 text-amber-400 border border-amber-500/50'
                          : 'bg-[rgb(var(--secondary))] text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))]'
                      }`}
                    >
                      {f === 'auto' ? 'Auto-detect' : f.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
              
              {/* Default Condition */}
              <div>
                <label className="block text-sm font-medium text-[rgb(var(--foreground))] mb-2">
                  Default Condition
                </label>
                <select
                  value={defaultCondition}
                  onChange={(e) => setDefaultCondition(e.target.value as InventoryCondition)}
                  className="w-full px-3 py-2 rounded-lg bg-[rgb(var(--secondary))] border border-[rgb(var(--border))] text-[rgb(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                >
                  {CONDITION_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              
              {/* Acquisition Source */}
              <div>
                <label className="block text-sm font-medium text-[rgb(var(--foreground))] mb-2">
                  Acquisition Source (optional)
                </label>
                <input
                  type="text"
                  value={acquisitionSource}
                  onChange={(e) => setAcquisitionSource(e.target.value)}
                  placeholder="e.g., TCGPlayer, Local Store, Trade"
                  className="w-full px-3 py-2 rounded-lg bg-[rgb(var(--secondary))] border border-[rgb(var(--border))] text-[rgb(var(--foreground))] placeholder:text-[rgb(var(--muted-foreground))] focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                />
              </div>
              
              {/* Content Input */}
              <div>
                <label className="block text-sm font-medium text-[rgb(var(--foreground))] mb-2">
                  Card List
                </label>
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder={`Enter your card list here...

Supported formats:
• Plaintext: "4x Lightning Bolt", "2 Black Lotus [FOIL]", "Force of Will (ALL) NM"
• CSV: card_name, set_code, quantity, condition, foil, price`}
                  rows={12}
                  className="w-full px-3 py-2 rounded-lg bg-[rgb(var(--secondary))] border border-[rgb(var(--border))] text-[rgb(var(--foreground))] placeholder:text-[rgb(var(--muted-foreground))] focus:outline-none focus:ring-2 focus:ring-amber-500/50 font-mono text-sm resize-none"
                />
              </div>
              
              {/* Example formats */}
              <div className="p-3 rounded-lg bg-[rgb(var(--secondary))]/50 border border-[rgb(var(--border))]">
                <div className="flex items-start gap-2">
                  <FileText className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
                  <div className="text-xs text-[rgb(var(--muted-foreground))]">
                    <p className="font-medium text-[rgb(var(--foreground))] mb-1">Supported plaintext formats:</p>
                    <code className="block">4x Lightning Bolt</code>
                    <code className="block">2 Black Lotus [FOIL]</code>
                    <code className="block">1x Force of Will (ALL) NM</code>
                    <code className="block">Tarmogoyf - Modern Masters - LP</code>
                  </div>
                </div>
              </div>
              
              {/* Submit Button */}
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="secondary" onClick={handleClose}>
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  onClick={() => importMutation.mutate()}
                  disabled={!content.trim() || importMutation.isPending}
                  className="bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
                >
                  {importMutation.isPending ? 'Importing...' : 'Import Cards'}
                </Button>
              </div>
              
              {importMutation.isError && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="w-4 h-4" />
                    Failed to import: {(importMutation.error as Error).message}
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Results View */
            <div className="space-y-4">
              {/* Summary */}
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 rounded-lg bg-[rgb(var(--secondary))] text-center">
                  <p className="text-2xl font-bold text-[rgb(var(--foreground))]">{result.total_lines}</p>
                  <p className="text-sm text-[rgb(var(--muted-foreground))]">Total Lines</p>
                </div>
                <div className="p-4 rounded-lg bg-green-500/10 text-center">
                  <p className="text-2xl font-bold text-green-400">{result.successful_imports}</p>
                  <p className="text-sm text-green-400/80">Imported</p>
                </div>
                <div className="p-4 rounded-lg bg-red-500/10 text-center">
                  <p className="text-2xl font-bold text-red-400">{result.failed_imports}</p>
                  <p className="text-sm text-red-400/80">Failed</p>
                </div>
              </div>
              
              {/* Results List */}
              <div className="space-y-2 max-h-[300px] overflow-y-auto">
                {result.items.map((item, idx) => (
                  <div
                    key={idx}
                    className={`p-3 rounded-lg border ${
                      item.success
                        ? 'bg-green-500/5 border-green-500/20'
                        : 'bg-red-500/5 border-red-500/20'
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      {item.success ? (
                        <CheckCircle2 className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
                      ) : (
                        <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-[rgb(var(--muted-foreground))]">
                            Line {item.line_number}:
                          </span>
                          {item.success ? (
                            <span className="font-medium text-[rgb(var(--foreground))]">
                              {item.card_name}
                            </span>
                          ) : (
                            <span className="text-red-400 text-sm">{item.error}</span>
                          )}
                        </div>
                        <code className="text-xs text-[rgb(var(--muted-foreground))] line-clamp-1">
                          {item.raw_line}
                        </code>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              
              {/* Close Button */}
              <div className="flex justify-end pt-2">
                <Button
                  variant="primary"
                  onClick={handleClose}
                  className="bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
                >
                  Done
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
