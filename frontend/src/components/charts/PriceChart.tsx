'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { format, formatDistanceToNow } from 'date-fns';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { formatCurrency } from '@/lib/utils';
import type { PricePoint, CardHistory } from '@/types';

interface PriceChartProps {
  data: PricePoint[];
  history?: CardHistory;  // Full history object with freshness info
  title?: string;
  height?: number;
  showFreshness?: boolean;  // Show data freshness indicator
  autoRefresh?: boolean;  // Auto-refresh data
  refreshInterval?: number;  // Refresh interval in seconds (default: 60)
}

const COLORS = [
  '#4a6cf7', // primary
  '#10b981', // green
  '#f59e0b', // amber
  '#ef4444', // red
  '#8b5cf6', // purple
];

export function PriceChart({ 
  data, 
  history,
  title = 'Price History', 
  height = 300,
  showFreshness = true,
  autoRefresh = false,
  refreshInterval = 60,
}: PriceChartProps) {
  // Group data by marketplace
  const marketplaces = Array.from(new Set(data.map((d) => d.marketplace)));
  
  // Transform data for recharts - include full timestamp for tooltip
  const chartData = data.reduce((acc, point) => {
    const dateKey = format(new Date(point.date), 'MMM d, HH:mm');
    const existing = acc.find((d) => d.date === dateKey);
    
    if (existing) {
      existing[point.marketplace] = point.price;
      // Store full timestamp for tooltip
      if (point.snapshot_time) {
        existing[`${point.marketplace}_time`] = point.snapshot_time;
        existing[`${point.marketplace}_age`] = point.data_age_minutes ?? 0;
      }
    } else {
      const entry: Record<string, string | number> = {
        date: dateKey,
        fullDate: point.date,
        [point.marketplace]: point.price,
      };
      if (point.snapshot_time) {
        entry[`${point.marketplace}_time`] = point.snapshot_time;
        entry[`${point.marketplace}_age`] = point.data_age_minutes ?? 0;
      }
      acc.push(entry);
    }
    
    return acc;
  }, [] as Record<string, string | number>[]);

  // Sort chart data chronologically by fullDate to ensure proper line rendering
  chartData.sort((a, b) => {
    const dateA = new Date(a.fullDate as string).getTime();
    const dateB = new Date(b.fullDate as string).getTime();
    return dateA - dateB;
  });

  // Get data freshness info
  const freshnessMinutes = history?.data_freshness_minutes;
  const latestSnapshot = history?.latest_snapshot_time;
  const isStale = freshnessMinutes !== undefined && freshnessMinutes > 60;  // Stale if > 1 hour
  const isVeryStale = freshnessMinutes !== undefined && freshnessMinutes > 1440;  // Very stale if > 24 hours

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>{title}</CardTitle>
          {showFreshness && freshnessMinutes !== undefined && (
            <div className="flex items-center gap-2 text-sm">
              <span className={`inline-flex items-center gap-1 ${
                isVeryStale ? 'text-red-500' : isStale ? 'text-amber-500' : 'text-green-500'
              }`}>
                <span className={`w-2 h-2 rounded-full ${
                  isVeryStale ? 'bg-red-500' : isStale ? 'bg-amber-500' : 'bg-green-500'
                } animate-pulse`} />
                {freshnessMinutes < 1 
                  ? 'Live' 
                  : freshnessMinutes < 60
                  ? `${freshnessMinutes}m ago`
                  : freshnessMinutes < 1440
                  ? `${Math.floor(freshnessMinutes / 60)}h ago`
                  : `${Math.floor(freshnessMinutes / 1440)}d ago`
                }
              </span>
              {latestSnapshot && (
                <span className="text-muted-foreground text-xs">
                  {formatDistanceToNow(new Date(latestSnapshot), { addSuffix: true })}
                </span>
              )}
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
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
              />
              <YAxis
                stroke="rgb(var(--muted-foreground))"
                fontSize={12}
                tickLine={false}
                tickFormatter={(value) => `$${value}`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgb(var(--card))',
                  border: '1px solid rgb(var(--border))',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: 'rgb(var(--foreground))' }}
                formatter={(value: number, name: string, props: any) => {
                  const age = props.payload[`${name}_age`];
                  const time = props.payload[`${name}_time`];
                  const ageText = age !== undefined ? ` (${age}m ago)` : '';
                  return [formatCurrency(value) + ageText, name];
                }}
                labelFormatter={(label: string, payload: any[]) => {
                  if (payload && payload[0]) {
                    const fullDate = payload[0].payload.fullDate;
                    if (fullDate) {
                      return format(new Date(fullDate), 'MMM d, yyyy HH:mm');
                    }
                  }
                  return label;
                }}
              />
              <Legend />
              {marketplaces.map((marketplace, index) => (
                <Line
                  key={marketplace}
                  type="monotone"
                  dataKey={marketplace}
                  name={marketplace}
                  stroke={COLORS[index % COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                  connectNulls={true}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

