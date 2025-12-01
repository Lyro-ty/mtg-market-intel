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
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
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
  title = 'Color Distribution by Format',
  height = 400,
  onWindowChange,
}: ColorDistributionChartProps) {
  const [selectedWindow, setSelectedWindow] = useState<'7d' | '30d'>(data.window);

  const handleWindowChange = (window: '7d' | '30d') => {
    setSelectedWindow(window);
    onWindowChange?.(window);
  };

  // Transform matrix data for stacked bar chart
  // Each format gets a bar, with segments for each color
  const chartData = data.formats.map((format, formatIndex) => {
    const point: Record<string, string | number> = {
      format,
    };
    
    // Add share for each color
    data.colors.forEach((color, colorIndex) => {
      const share = data.matrix[formatIndex]?.[colorIndex] || 0;
      point[color] = share * 100; // Convert to percentage
    });
    
    return point;
  });

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
          <Button
            variant={selectedWindow === '7d' ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => handleWindowChange('7d')}
          >
            7D
          </Button>
          <Button
            variant={selectedWindow === '30d' ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => handleWindowChange('30d')}
          >
            30D
          </Button>
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
              />
              <XAxis
                type="number"
                domain={[0, 100]}
                stroke="rgb(var(--muted-foreground))"
                fontSize={12}
                tickLine={false}
                tickFormatter={(value) => `${value}%`}
              />
              <YAxis
                type="category"
                dataKey="format"
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
                labelStyle={{ color: 'rgb(var(--foreground))' }}
                formatter={(value: number, name: string) => [
                  formatPercent(value / 100),
                  COLOR_LABELS[name] || name,
                ]}
              />
              <Legend
                formatter={(value) => COLOR_LABELS[value] || value}
              />
              {data.colors.map((color) => (
                <Bar
                  key={color}
                  dataKey={color}
                  stackId="1"
                  fill={COLOR_MAP[color] || '#6b7280'}
                  name={color}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

