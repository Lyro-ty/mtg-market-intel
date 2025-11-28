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
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { formatCurrency } from '@/lib/utils';
import type { MarketplacePrice } from '@/types';

interface SpreadChartProps {
  data: MarketplacePrice[];
  title?: string;
  height?: number;
}

export function SpreadChart({
  data,
  title = 'Price Comparison',
  height = 250,
}: SpreadChartProps) {
  const chartData = data.map((item) => ({
    marketplace: item.marketplace_name,
    price: item.price,
  }));

  // Sort by price
  chartData.sort((a, b) => a.price - b.price);

  const minPrice = Math.min(...chartData.map((d) => d.price));
  const maxPrice = Math.max(...chartData.map((d) => d.price));

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
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
                formatter={(value: number) => [formatCurrency(value), 'Price']}
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

