'use client';

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { format } from 'date-fns';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { formatCurrency, formatNumber } from '@/lib/utils';
import type { VolumeByFormat } from '@/types';

interface VolumeByFormatChartProps {
  data: VolumeByFormat;
  title?: string;
  height?: number;
}

const COLORS = [
  '#4a6cf7', // primary blue
  '#10b981', // green
  '#f59e0b', // amber
  '#ef4444', // red
  '#8b5cf6', // purple
  '#06b6d4', // cyan
  '#ec4899', // pink
];

export function VolumeByFormatChart({
  data,
  title = 'Volume by Format',
  height = 350,
}: VolumeByFormatChartProps) {
  // Transform data for stacked area chart
  // Group all points by timestamp
  const allDates = new Set<string>();
  data.formats.forEach((format) => {
    format.data.forEach((point) => {
      allDates.add(point.timestamp);
    });
  });

  const sortedDates = Array.from(allDates).sort();

  const chartData = sortedDates.map((timestamp) => {
    const date = new Date(timestamp);
    const point: Record<string, string | number> = {
      date: format(date, 'MMM d'),
      fullDate: timestamp,
    };

    // Add volume for each format
    data.formats.forEach((format) => {
      const formatPoint = format.data.find((p) => p.timestamp === timestamp);
      point[format.format] = formatPoint ? formatPoint.volume : 0;
    });

    return point;
  });

  // Calculate total volume across all formats
  const totalVolume = data.formats.reduce((sum, format) => {
    return (
      sum +
      format.data.reduce((formatSum, point) => formatSum + point.volume, 0)
    );
  }, 0);

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{title}</CardTitle>
          {data.isMockData && (
            <p className="text-xs text-[rgb(var(--muted-foreground))] mt-1">
              Showing mock data
            </p>
          )}
          <p className="text-sm text-[rgb(var(--muted-foreground))] mt-1">
            Total volume: {formatCurrency(totalVolume)}
          </p>
        </div>
      </CardHeader>
      <CardContent>
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                {data.formats.map((format, index) => (
                  <linearGradient
                    key={format.format}
                    id={`color-${format.format.replace(/\s+/g, '-')}-${index}`}
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="5%"
                      stopColor={COLORS[index % COLORS.length]}
                      stopOpacity={0.8}
                    />
                    <stop
                      offset="95%"
                      stopColor={COLORS[index % COLORS.length]}
                      stopOpacity={0.1}
                    />
                  </linearGradient>
                ))}
              </defs>
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
              />
              <YAxis
                stroke="rgb(var(--muted-foreground))"
                fontSize={12}
                tickLine={false}
                tickFormatter={(value) => {
                  if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`;
                  if (value >= 1000) return `$${(value / 1000).toFixed(0)}K`;
                  return `$${value}`;
                }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgb(var(--card))',
                  border: '1px solid rgb(var(--border))',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: 'rgb(var(--foreground))' }}
                formatter={(value: number) => [formatCurrency(value), 'Volume']}
              />
              <Legend />
              {data.formats.map((format, index) => (
                <Area
                  key={format.format}
                  type="monotone"
                  dataKey={format.format}
                  name={format.format}
                  stackId="1"
                  stroke={COLORS[index % COLORS.length]}
                  fill={`url(#color-${format.format.replace(/\s+/g, '-')}-${index})`}
                  strokeWidth={2}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

