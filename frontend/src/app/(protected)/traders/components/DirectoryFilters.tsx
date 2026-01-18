'use client';

import { useState, useEffect, useCallback } from 'react';
import { Search, Filter, Grid, List, X, ChevronDown, ChevronUp } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

export interface DirectoryFiltersState {
  q: string;
  sort: 'discovery_score' | 'reputation' | 'trades' | 'newest' | 'best_match';
  reputationTier: string[];
  frameTier: string[];
  cardType: string[];
  format: string[];
  shipping: string[];
  onlineOnly: boolean;
  verifiedOnly: boolean;
}

interface DirectoryFiltersProps {
  filters: DirectoryFiltersState;
  onChange: (filters: DirectoryFiltersState) => void;
  viewMode: 'grid' | 'list';
  onViewModeChange: (mode: 'grid' | 'list') => void;
  className?: string;
}

// Filter options
const REPUTATION_TIERS = [
  { value: 'new', label: 'New' },
  { value: 'established', label: 'Established' },
  { value: 'trusted', label: 'Trusted' },
  { value: 'elite', label: 'Elite' },
];

const FRAME_TIERS = [
  { value: 'bronze', label: 'Bronze' },
  { value: 'silver', label: 'Silver' },
  { value: 'gold', label: 'Gold' },
  { value: 'platinum', label: 'Platinum' },
];

const CARD_TYPES = [
  { value: 'collector', label: 'Collector' },
  { value: 'trader', label: 'Trader' },
  { value: 'brewer', label: 'Brewer' },
  { value: 'investor', label: 'Investor' },
];

const MTG_FORMATS = [
  { value: 'standard', label: 'Standard' },
  { value: 'modern', label: 'Modern' },
  { value: 'pioneer', label: 'Pioneer' },
  { value: 'legacy', label: 'Legacy' },
  { value: 'vintage', label: 'Vintage' },
  { value: 'commander', label: 'Commander' },
  { value: 'pauper', label: 'Pauper' },
];

const SHIPPING_OPTIONS = [
  { value: 'local', label: 'Local Only' },
  { value: 'domestic', label: 'Domestic' },
  { value: 'international', label: 'International' },
];

const SORT_OPTIONS = [
  { value: 'discovery_score', label: 'Relevance' },
  { value: 'reputation', label: 'Reputation' },
  { value: 'trades', label: 'Most Trades' },
  { value: 'newest', label: 'Newest Members' },
  { value: 'best_match', label: 'Best Match' },
] as const;

export function DirectoryFilters({
  filters,
  onChange,
  viewMode,
  onViewModeChange,
  className,
}: DirectoryFiltersProps) {
  const [searchInput, setSearchInput] = useState(filters.q);
  const [isExpanded, setIsExpanded] = useState(false);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchInput !== filters.q) {
        onChange({ ...filters, q: searchInput });
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput, filters, onChange]);

  // Toggle array filter
  const toggleArrayFilter = useCallback(
    (
      key: 'reputationTier' | 'frameTier' | 'cardType' | 'format' | 'shipping',
      value: string
    ) => {
      const currentValues = filters[key];
      const newValues = currentValues.includes(value)
        ? currentValues.filter((v) => v !== value)
        : [...currentValues, value];
      onChange({ ...filters, [key]: newValues });
    },
    [filters, onChange]
  );

  // Clear all filters
  const clearFilters = useCallback(() => {
    setSearchInput('');
    onChange({
      q: '',
      sort: 'discovery_score',
      reputationTier: [],
      frameTier: [],
      cardType: [],
      format: [],
      shipping: [],
      onlineOnly: false,
      verifiedOnly: false,
    });
  }, [onChange]);

  // Count active filters
  const activeFilterCount =
    filters.reputationTier.length +
    filters.frameTier.length +
    filters.cardType.length +
    filters.format.length +
    filters.shipping.length +
    (filters.onlineOnly ? 1 : 0) +
    (filters.verifiedOnly ? 1 : 0);

  return (
    <div className={cn('space-y-4', className)}>
      {/* Search and View Toggle Row */}
      <div className="flex flex-col sm:flex-row gap-4">
        {/* Search Input */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search traders by name..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Sort Select */}
        <Select
          value={filters.sort}
          onValueChange={(value) =>
            onChange({
              ...filters,
              sort: value as DirectoryFiltersState['sort'],
            })
          }
        >
          <SelectTrigger className="w-full sm:w-[180px]">
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* View Mode Toggle */}
        <div className="flex gap-1 border border-border rounded-md p-1">
          <Button
            variant={viewMode === 'grid' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => onViewModeChange('grid')}
            className={cn(
              viewMode === 'grid' && 'bg-primary text-primary-foreground'
            )}
          >
            <Grid className="h-4 w-4" />
          </Button>
          <Button
            variant={viewMode === 'list' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => onViewModeChange('list')}
            className={cn(
              viewMode === 'list' && 'bg-primary text-primary-foreground'
            )}
          >
            <List className="h-4 w-4" />
          </Button>
        </div>

        {/* Filter Toggle Button */}
        <Button
          variant="outline"
          onClick={() => setIsExpanded(!isExpanded)}
          className="relative"
        >
          <Filter className="h-4 w-4 mr-2" />
          Filters
          {activeFilterCount > 0 && (
            <Badge
              variant="destructive"
              className="absolute -top-2 -right-2 h-5 w-5 p-0 flex items-center justify-center text-xs"
            >
              {activeFilterCount}
            </Badge>
          )}
          {isExpanded ? (
            <ChevronUp className="h-4 w-4 ml-2" />
          ) : (
            <ChevronDown className="h-4 w-4 ml-2" />
          )}
        </Button>
      </div>

      {/* Expanded Filters */}
      {isExpanded && (
        <div className="p-4 bg-card border border-border rounded-lg space-y-4 animate-in slide-in-from-top-2 duration-200">
          {/* Quick Toggles */}
          <div className="flex flex-wrap gap-2">
            <Button
              variant={filters.onlineOnly ? 'default' : 'outline'}
              size="sm"
              onClick={() =>
                onChange({ ...filters, onlineOnly: !filters.onlineOnly })
              }
              className={cn(
                filters.onlineOnly &&
                  'bg-green-600 hover:bg-green-700 text-white'
              )}
            >
              <span className="h-2 w-2 rounded-full bg-current mr-2" />
              Online Now
            </Button>
            <Button
              variant={filters.verifiedOnly ? 'default' : 'outline'}
              size="sm"
              onClick={() =>
                onChange({ ...filters, verifiedOnly: !filters.verifiedOnly })
              }
              className={cn(
                filters.verifiedOnly &&
                  'bg-blue-600 hover:bg-blue-700 text-white'
              )}
            >
              Verified Only
            </Button>
          </div>

          {/* Filter Groups */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Reputation Tier */}
            <FilterGroup
              label="Reputation"
              options={REPUTATION_TIERS}
              selected={filters.reputationTier}
              onToggle={(value) => toggleArrayFilter('reputationTier', value)}
            />

            {/* Card Type */}
            <FilterGroup
              label="Trader Type"
              options={CARD_TYPES}
              selected={filters.cardType}
              onToggle={(value) => toggleArrayFilter('cardType', value)}
            />

            {/* MTG Formats */}
            <FilterGroup
              label="Formats"
              options={MTG_FORMATS}
              selected={filters.format}
              onToggle={(value) => toggleArrayFilter('format', value)}
            />

            {/* Shipping */}
            <FilterGroup
              label="Shipping"
              options={SHIPPING_OPTIONS}
              selected={filters.shipping}
              onToggle={(value) => toggleArrayFilter('shipping', value)}
            />

            {/* Frame Tier */}
            <FilterGroup
              label="Frame Tier"
              options={FRAME_TIERS}
              selected={filters.frameTier}
              onToggle={(value) => toggleArrayFilter('frameTier', value)}
            />
          </div>

          {/* Clear Filters */}
          {activeFilterCount > 0 && (
            <div className="flex justify-end">
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                <X className="h-4 w-4 mr-2" />
                Clear All Filters
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Active Filter Pills (when collapsed) */}
      {!isExpanded && activeFilterCount > 0 && (
        <div className="flex flex-wrap gap-2">
          {filters.onlineOnly && (
            <FilterPill
              label="Online"
              onRemove={() => onChange({ ...filters, onlineOnly: false })}
            />
          )}
          {filters.verifiedOnly && (
            <FilterPill
              label="Verified"
              onRemove={() => onChange({ ...filters, verifiedOnly: false })}
            />
          )}
          {filters.reputationTier.map((tier) => (
            <FilterPill
              key={tier}
              label={tier}
              onRemove={() => toggleArrayFilter('reputationTier', tier)}
            />
          ))}
          {filters.cardType.map((type) => (
            <FilterPill
              key={type}
              label={type}
              onRemove={() => toggleArrayFilter('cardType', type)}
            />
          ))}
          {filters.format.map((fmt) => (
            <FilterPill
              key={fmt}
              label={fmt}
              onRemove={() => toggleArrayFilter('format', fmt)}
            />
          ))}
          {filters.shipping.map((ship) => (
            <FilterPill
              key={ship}
              label={ship}
              onRemove={() => toggleArrayFilter('shipping', ship)}
            />
          ))}
          {filters.frameTier.map((tier) => (
            <FilterPill
              key={tier}
              label={`${tier} frame`}
              onRemove={() => toggleArrayFilter('frameTier', tier)}
            />
          ))}
          <Button
            variant="ghost"
            size="sm"
            onClick={clearFilters}
            className="h-7 text-xs"
          >
            Clear all
          </Button>
        </div>
      )}
    </div>
  );
}

// Filter Group Component
interface FilterGroupProps {
  label: string;
  options: Array<{ value: string; label: string }>;
  selected: string[];
  onToggle: (value: string) => void;
}

function FilterGroup({ label, options, selected, onToggle }: FilterGroupProps) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-muted-foreground">
        {label}
      </label>
      <div className="flex flex-wrap gap-1">
        {options.map((option) => (
          <Button
            key={option.value}
            variant={selected.includes(option.value) ? 'default' : 'outline'}
            size="sm"
            onClick={() => onToggle(option.value)}
            className={cn(
              'h-7 text-xs',
              selected.includes(option.value) &&
                'bg-[rgb(var(--accent))] hover:bg-[rgb(var(--accent))]/90'
            )}
          >
            {option.label}
          </Button>
        ))}
      </div>
    </div>
  );
}

// Filter Pill Component
interface FilterPillProps {
  label: string;
  onRemove: () => void;
}

function FilterPill({ label, onRemove }: FilterPillProps) {
  return (
    <Badge
      variant="secondary"
      className="pl-2 pr-1 py-1 flex items-center gap-1 capitalize"
    >
      {label}
      <button
        onClick={onRemove}
        className="hover:bg-muted rounded-full p-0.5"
        aria-label={`Remove ${label} filter`}
      >
        <X className="h-3 w-3" />
      </button>
    </Badge>
  );
}

export default DirectoryFilters;
