'use client';

import { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from 'recharts';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { formatPercent } from '@/lib/utils';
import type { ColorDistribution } from '@/types';

interface ColorDistributionChartProps {
  data: ColorDistribution;
  title?: string;
  height?: number;
  onWindowChange?: (window: '7d' | '30d') => void;
}

const COLOR_MAP: Record<string, string> = {
  W: '#f9fafb', // White
  U: '#3b82f6', // Blue
  B: '#1f2937', // Black
  R: '#ef4444', // Red
  G: '#10b981', // Green
  Multicolor: '#8b5cf6', // Purple
  Colorless: '#6b7280', // Gray
};

const COLOR_LABELS: Record<string, string> = {
  W: 'White',
  U: 'Blue',
  B: 'Black',
  R: 'Red',
  G: 'Green',
  Multicolor: 'Multicolor',
  Colorless: 'Colorless',
};

export function ColorDistributionChart({
  data,
  title = 'Color Distribution',
  height = 400,
}: ColorDistributionChartProps) {
  // Transform distribution data for bar chart
  const chartData = data.colors.map((color) => ({
    color: COLOR_LABELS[color] || color,
    value: data.distribution[color] || 0,
    colorCode: color,
  }));

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
        </div>
      </CardHeader>
      <CardContent>
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgb(var(--border))"
                opacity={0.5}
              />
              <XAxis
                dataKey="color"
                stroke="rgb(var(--muted-foreground))"
                fontSize={12}
                tickLine={false}
              />
              <YAxis
                stroke="rgb(var(--muted-foreground))"
                fontSize={12}
                tickLine={false}
                tickFormatter={(value) => `${value}%`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgb(var(--card))',
                  border: '1px solid rgb(var(--border))',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: 'rgb(var(--foreground))' }}
                formatter={(value: number) => [`${value.toFixed(2)}%`, 'Percentage']}
              />
              <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLOR_MAP[entry.colorCode] || '#6b7280'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}


