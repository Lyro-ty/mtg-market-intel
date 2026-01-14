import { Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { TradeStatus } from "@/types";

interface TradeStatusBadgeProps {
  status: TradeStatus;
  size?: 'sm' | 'md';
}

const statusConfig: Record<
  TradeStatus,
  { variant: 'success' | 'warning' | 'danger' | 'info' | 'secondary'; showCheckmark?: boolean }
> = {
  pending: { variant: 'warning' },
  accepted: { variant: 'success' },
  declined: { variant: 'danger' },
  countered: { variant: 'info' },
  expired: { variant: 'secondary' },
  completed: { variant: 'success', showCheckmark: true },
  cancelled: { variant: 'secondary' },
};

function capitalizeStatus(status: TradeStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export function TradeStatusBadge({ status, size }: TradeStatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <Badge variant={config.variant} size={size}>
      {config.showCheckmark && <Check className="mr-1 h-3 w-3" />}
      {capitalizeStatus(status)}
    </Badge>
  );
}
