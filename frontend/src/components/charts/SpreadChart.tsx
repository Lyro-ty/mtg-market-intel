'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { formatDistanceToNow } from 'date-fns';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { formatCurrency } from '@/lib/utils';
import type { MarketplacePrice } from '@/types';

interface SpreadChartProps {
  data: MarketplacePrice[];
  title?: string;
  height?: number;
  showFreshness?: boolean;
}

export function SpreadChart({
  data,
  title = 'Price Comparison',
  height = 250,
  showFreshness = true,
}: SpreadChartProps) {
  // Handle empty or missing data
  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center" style={{ height }}>
            <span className="text-[rgb(var(--muted-foreground))]">
              No price data available
            </span>
          </div>
        </CardContent>
      </Card>
    );
  }

  const chartData = data.map((item) => ({
    marketplace: item.marketplace_name,
    price: item.price,
    last_updated: item.last_updated,
  }));

  // Sort by price
  chartData.sort((a, b) => a.price - b.price);

  const minPrice = Math.min(...chartData.map((d) => d.price));
  const maxPrice = Math.max(...chartData.map((d) => d.price));
  
  // Get most recent update time
  const latestUpdate = data.length > 0 
    ? Math.max(...data.map(d => new Date(d.last_updated).getTime()))
    : null;
  const latestUpdateDate = latestUpdate ? new Date(latestUpdate) : null;
  const freshnessMinutes = latestUpdateDate 
    ? Math.floor((Date.now() - latestUpdateDate.getTime()) / 60000)
    : null;
  const isStale = freshnessMinutes !== null && freshnessMinutes > 60;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>{title}</CardTitle>
          {showFreshness && latestUpdateDate && (
            <div className="flex items-center gap-2 text-sm">
              <span className={`inline-flex items-center gap-1 ${
                isStale ? 'text-amber-500' : 'text-green-500'
              }`}>
                <span className={`w-2 h-2 rounded-full ${
                  isStale ? 'bg-amber-500' : 'bg-green-500'
                } animate-pulse`} />
                {freshnessMinutes !== null && freshnessMinutes < 1 
                  ? 'Live' 
                  : freshnessMinutes !== null && freshnessMinutes < 60
                  ? `${freshnessMinutes}m ago`
                  : formatDistanceToNow(latestUpdateDate, { addSuffix: true })
                }
              </span>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical">
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgb(var(--border))"
                opacity={0.5}
                horizontal={false}
              />
              <XAxis
                type="number"
                stroke="rgb(var(--muted-foreground))"
                fontSize={12}
                tickLine={false}
                tickFormatter={(value) => `$${value}`}
              />
              <YAxis
                type="category"
                dataKey="marketplace"
                stroke="rgb(var(--muted-foreground))"
                fontSize={12}
                tickLine={false}
                width={100}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgb(var(--card))',
                  border: '1px solid rgb(var(--border))',
                  borderRadius: '8px',
                }}
                formatter={(value: number, name: string, props: any) => {
                  const lastUpdated = props.payload.last_updated;
                  const updateText = lastUpdated 
                    ? ` (${formatDistanceToNow(new Date(lastUpdated), { addSuffix: true })})`
                    : '';
                  return [formatCurrency(value) + updateText, 'Price'];
                }}
              />
              <Bar dataKey="price" radius={[0, 4, 4, 0]}>
                {chartData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={
                      entry.price === minPrice
                        ? '#10b981' // green for lowest
                        : entry.price === maxPrice
                        ? '#ef4444' // red for highest
                        : '#4a6cf7' // primary for others
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

