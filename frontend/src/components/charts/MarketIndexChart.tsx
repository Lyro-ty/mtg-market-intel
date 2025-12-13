'use client';

import { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { format } from 'date-fns';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { formatPercent } from '@/lib/utils';
import type { MarketIndex } from '@/types';

interface MarketIndexChartProps {
  data: MarketIndex;
  title?: string;
  height?: number;
  onRangeChange?: (range: '7d' | '30d' | '90d' | '1y') => void;
  onFoilChange?: (isFoil: boolean | undefined) => void;
  showFoilToggle?: boolean;
}

const RANGES: Array<{ value: '7d' | '30d' | '90d' | '1y'; label: string }> = [
  { value: '7d', label: '7D' },
  { value: '30d', label: '30D' },
  { value: '90d', label: '90D' },
  { value: '1y', label: '1Y' },
];

export function MarketIndexChart({
  data,
  title = 'Global MTG Market Index',
  height = 350,
  onRangeChange,
  onFoilChange,
  showFoilToggle = true,
}: MarketIndexChartProps) {
  const [selectedRange, setSelectedRange] = useState<'7d' | '30d' | '90d' | '1y'>(data?.range || '7d');
  const [selectedFoil, setSelectedFoil] = useState<boolean | undefined>(undefined);
  const currencyLabel = data?.currency ?? 'USD';

  // Sync selectedRange with data.range when data changes
  useEffect(() => {
    if (data?.range && data.range !== selectedRange) {
      setSelectedRange(data.range);
    }
  }, [data?.range, selectedRange]);

  const handleRangeChange = (range: '7d' | '30d' | '90d' | '1y') => {
    setSelectedRange(range);
    onRangeChange?.(range);
  };

  const handleFoilChange = (isFoil: boolean | undefined) => {
    setSelectedFoil(isFoil);
    onFoilChange?.(isFoil);
  };

  // Handle empty or missing data
  if (!data || !data.points || data.points.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-64 text-[rgb(var(--muted-foreground))]">
            No data available
          </div>
        </CardContent>
      </Card>
    );
  }

  // Transform data for chart
  const chartData = data.points
    .filter((point) => point && point.timestamp && typeof point.indexValue === 'number')
    .map((point) => {
      const date = new Date(point.timestamp);
      // Use more detailed format for higher frequency data
      // If we have many points (more than 50), show time as well
      const dateFormat = data.points.length > 50 
        ? format(date, 'MMM d HH:mm')
        : format(date, 'MMM d');
      return {
        date: dateFormat,
        fullDate: point.timestamp,
        index: point.indexValue,
        // Calculate % change from previous point
        change: null as number | null,
      };
    });

  // If no valid data points after filtering, show empty state
  if (chartData.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-64 text-[rgb(var(--muted-foreground))]">
            No valid data points available
          </div>
        </CardContent>
      </Card>
    );
  }

  // Calculate change from previous point
  for (let i = 1; i < chartData.length; i++) {
    const prev = chartData[i - 1].index;
    const curr = chartData[i].index;
    if (prev && curr) {
      chartData[i].change = ((curr - prev) / prev) * 100;
    }
  }

  const baseValue = chartData[0]?.index || 100;
  const currentValue = chartData[chartData.length - 1]?.index || 100;
  const totalChange = ((currentValue - baseValue) / baseValue) * 100;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>{title}</CardTitle>
          {data.isMockData && (
            <p className="text-xs text-[rgb(var(--muted-foreground))] mt-1">
              Showing mock data
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {RANGES.map((range) => (
            <Button
              key={range.value}
              variant={selectedRange === range.value ? 'primary' : 'secondary'}
              size="sm"
              onClick={() => handleRangeChange(range.value)}
            >
              {range.label}
            </Button>
          ))}
        </div>
        <div className="flex gap-2 mt-2">
          {showFoilToggle && (
            <>
              <Button
                variant={selectedFoil === undefined ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => handleFoilChange(undefined)}
              >
                All Cards
              </Button>
              <Button
                variant={selectedFoil === false ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => handleFoilChange(false)}
              >
                Non-Foil
              </Button>
              <Button
                variant={selectedFoil === true ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => handleFoilChange(true)}
              >
                Foil
              </Button>
            </>
          )}
        </div>
        <div className="text-xs text-[rgb(var(--muted-foreground))] mt-1">
          Currency: {currencyLabel}
        </div>
      </CardHeader>
      <CardContent>
        <div className="mb-4">
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-[rgb(var(--foreground))]">
              {currentValue.toFixed(2)}
            </span>
            <span
              className={`text-sm font-medium ${
                totalChange >= 0 ? 'text-green-500' : 'text-red-500'
              }`}
            >
              {formatPercent(totalChange)}
            </span>
            <span className="text-sm text-[rgb(var(--muted-foreground))]">
              vs baseline
            </span>
          </div>
        </div>
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgb(var(--border))"
                opacity={0.5}
              />
              <XAxis
                dataKey="date"
                stroke="rgb(var(--muted-foreground))"
                fontSize={12}
                tickLine={false}
                angle={-45}
                textAnchor="end"
                height={60}
                interval={data.points.length > 50 ? Math.floor(data.points.length / 10) : 0}
              />
              <YAxis
                stroke="rgb(var(--muted-foreground))"
                fontSize={12}
                tickLine={false}
                tickFormatter={(value) => value.toFixed(0)}
                domain={['auto', 'auto']}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgb(var(--card))',
                  border: '1px solid rgb(var(--border))',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: 'rgb(var(--foreground))' }}
                formatter={(value: number, name: string, props: any) => {
                  const change = props.payload.change;
                  const changeText = change !== null ? ` (${formatPercent(change)})` : '';
                  return [`${value.toFixed(2)}${changeText}`, 'Index Value'];
                }}
                labelFormatter={(label) => `Date: ${label}`}
              />
              <Line
                type="monotone"
                dataKey="index"
                name="Market Index"
                stroke="#4a6cf7"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

