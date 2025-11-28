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
import { format } from 'date-fns';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { formatCurrency } from '@/lib/utils';
import type { PricePoint } from '@/types';

interface PriceChartProps {
  data: PricePoint[];
  title?: string;
  height?: number;
}

const COLORS = [
  '#4a6cf7', // primary
  '#10b981', // green
  '#f59e0b', // amber
  '#ef4444', // red
  '#8b5cf6', // purple
];

export function PriceChart({ data, title = 'Price History', height = 300 }: PriceChartProps) {
  // Group data by marketplace
  const marketplaces = Array.from(new Set(data.map((d) => d.marketplace)));
  
  // Transform data for recharts
  const chartData = data.reduce((acc, point) => {
    const dateKey = format(new Date(point.date), 'MMM d');
    const existing = acc.find((d) => d.date === dateKey);
    
    if (existing) {
      existing[point.marketplace] = point.price;
    } else {
      acc.push({
        date: dateKey,
        [point.marketplace]: point.price,
      });
    }
    
    return acc;
  }, [] as Record<string, string | number>[]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
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
                formatter={(value: number) => [formatCurrency(value), '']}
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
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

