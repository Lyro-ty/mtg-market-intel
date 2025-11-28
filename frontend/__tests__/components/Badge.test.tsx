import { render, screen } from '@testing-library/react';
import { Badge, ActionBadge } from '@/components/ui/Badge';

describe('Badge', () => {
  it('renders children correctly', () => {
    render(<Badge>Test Badge</Badge>);
    expect(screen.getByText('Test Badge')).toBeInTheDocument();
  });

  it('applies default variant styles', () => {
    render(<Badge>Default</Badge>);
    const badge = screen.getByText('Default');
    expect(badge).toHaveClass('bg-[rgb(var(--secondary))]');
  });

  it('applies success variant styles', () => {
    render(<Badge variant="success">Success</Badge>);
    const badge = screen.getByText('Success');
    expect(badge).toHaveClass('bg-green-100');
  });

  it('applies danger variant styles', () => {
    render(<Badge variant="danger">Danger</Badge>);
    const badge = screen.getByText('Danger');
    expect(badge).toHaveClass('bg-red-100');
  });
});

describe('ActionBadge', () => {
  it('renders BUY action with success styling', () => {
    render(<ActionBadge action="BUY" />);
    const badge = screen.getByText('BUY');
    expect(badge).toBeInTheDocument();
  });

  it('renders SELL action with danger styling', () => {
    render(<ActionBadge action="SELL" />);
    const badge = screen.getByText('SELL');
    expect(badge).toBeInTheDocument();
  });

  it('renders HOLD action with warning styling', () => {
    render(<ActionBadge action="HOLD" />);
    const badge = screen.getByText('HOLD');
    expect(badge).toBeInTheDocument();
  });
});

