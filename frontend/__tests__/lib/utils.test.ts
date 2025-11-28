import {
  formatCurrency,
  formatPercent,
  formatNumber,
  getPriceChangeColor,
  getActionColor,
  getRarityColor,
  truncate,
} from '@/lib/utils';

describe('formatCurrency', () => {
  it('formats positive numbers correctly', () => {
    expect(formatCurrency(10.5)).toBe('$10.50');
    expect(formatCurrency(1234.56)).toBe('$1,234.56');
  });

  it('handles undefined and null', () => {
    expect(formatCurrency(undefined)).toBe('-');
    expect(formatCurrency(null)).toBe('-');
  });

  it('handles zero', () => {
    expect(formatCurrency(0)).toBe('$0.00');
  });
});

describe('formatPercent', () => {
  it('formats positive percentages with plus sign', () => {
    expect(formatPercent(10.5)).toBe('+10.5%');
  });

  it('formats negative percentages', () => {
    expect(formatPercent(-5.5)).toBe('-5.5%');
  });

  it('handles zero', () => {
    expect(formatPercent(0)).toBe('0.0%');
  });

  it('handles undefined and null', () => {
    expect(formatPercent(undefined)).toBe('-');
    expect(formatPercent(null)).toBe('-');
  });
});

describe('formatNumber', () => {
  it('formats integers correctly', () => {
    expect(formatNumber(1234)).toBe('1,234');
  });

  it('respects decimal places', () => {
    expect(formatNumber(1234.567, 2)).toBe('1,234.57');
  });

  it('handles undefined and null', () => {
    expect(formatNumber(undefined)).toBe('-');
    expect(formatNumber(null)).toBe('-');
  });
});

describe('getPriceChangeColor', () => {
  it('returns green for positive changes', () => {
    expect(getPriceChangeColor(5)).toBe('text-green-500');
  });

  it('returns red for negative changes', () => {
    expect(getPriceChangeColor(-5)).toBe('text-red-500');
  });

  it('returns gray for zero', () => {
    expect(getPriceChangeColor(0)).toBe('text-gray-500');
  });

  it('returns gray for undefined', () => {
    expect(getPriceChangeColor(undefined)).toBe('text-gray-500');
  });
});

describe('getActionColor', () => {
  it('returns correct color for BUY', () => {
    expect(getActionColor('BUY')).toContain('green');
  });

  it('returns correct color for SELL', () => {
    expect(getActionColor('SELL')).toContain('red');
  });

  it('returns correct color for HOLD', () => {
    expect(getActionColor('HOLD')).toContain('yellow');
  });
});

describe('getRarityColor', () => {
  it('returns orange for mythic', () => {
    expect(getRarityColor('mythic')).toBe('text-orange-500');
  });

  it('returns yellow for rare', () => {
    expect(getRarityColor('rare')).toBe('text-yellow-500');
  });

  it('handles undefined', () => {
    expect(getRarityColor(undefined)).toBe('text-gray-500');
  });
});

describe('truncate', () => {
  it('truncates long strings', () => {
    expect(truncate('This is a long string', 10)).toBe('This is...');
  });

  it('does not truncate short strings', () => {
    expect(truncate('Short', 10)).toBe('Short');
  });
});

