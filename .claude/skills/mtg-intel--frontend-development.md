---
name: mtg-intel:frontend-development
description: Use when creating or modifying React components, pages, or hooks in the Next.js frontend
---

# Frontend Development Skill for Dualcaster Deals

Follow these patterns when developing frontend components and pages.

## File Structure

```
frontend/src/
├── app/
│   ├── (protected)/           # Auth-required routes
│   │   └── {feature}/
│   │       └── page.tsx       # Page component
│   └── (public)/              # Public routes
│       └── {feature}/
│           └── page.tsx
├── components/
│   ├── {feature}/             # Feature-specific components
│   │   ├── {Feature}Card.tsx
│   │   └── {Feature}List.tsx
│   └── ui/                    # Shared UI components (shadcn)
├── lib/
│   └── api/
│       └── {feature}.ts       # API functions
└── types/
    ├── index.ts               # Re-exports
    └── api.generated.ts       # Auto-generated (don't edit!)
```

## Page Pattern

```tsx
// frontend/src/app/(protected)/{feature}/page.tsx
'use client';

import { useQuery } from '@tanstack/react-query';
import { get{Feature}s } from '@/lib/api/{feature}';
import { {Feature}List } from '@/components/{feature}/{Feature}List';
import { LoadingSpinner } from '@/components/ui/loading-spinner';

export default function {Feature}Page() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['{feature}s'],
    queryFn: get{Feature}s,
  });

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return (
      <div className="text-red-500">
        Error loading {feature}s: {error.message}
      </div>
    );
  }

  return (
    <div className="container mx-auto py-6">
      <h1 className="text-2xl font-bold mb-6">{Feature}s</h1>
      <{Feature}List items={data ?? []} />
    </div>
  );
}
```

## Component Pattern

```tsx
// frontend/src/components/{feature}/{Feature}Card.tsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { {Feature} } from '@/types';

interface {Feature}CardProps {
  item: {Feature};
  onSelect?: (item: {Feature}) => void;
}

export function {Feature}Card({ item, onSelect }: {Feature}CardProps) {
  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow"
      onClick={() => onSelect?.(item)}
    >
      <CardHeader>
        <CardTitle>{item.name}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          {item.description}
        </p>
      </CardContent>
    </Card>
  );
}
```

## API Function Pattern

```typescript
// frontend/src/lib/api/{feature}.ts
import { fetchApi } from '@/lib/api';
import type { {Feature}, {Feature}Create } from '@/types';

export async function get{Feature}s(): Promise<{Feature}[]> {
  return fetchApi('/api/{feature}/');
}

export async function get{Feature}(id: number): Promise<{Feature}> {
  return fetchApi(`/api/{feature}/${id}`);
}

export async function create{Feature}(data: {Feature}Create): Promise<{Feature}> {
  return fetchApi('/api/{feature}/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function update{Feature}(
  id: number,
  data: Partial<{Feature}>
): Promise<{Feature}> {
  return fetchApi(`/api/{feature}/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function delete{Feature}(id: number): Promise<void> {
  return fetchApi(`/api/{feature}/${id}`, {
    method: 'DELETE',
  });
}
```

## Type Pattern

Types are auto-generated from the backend OpenAPI schema.

```typescript
// frontend/src/types/index.ts
// Re-export generated types with friendly names
export type {
  {Feature}Response as {Feature},
  {Feature}Create,
  {Feature}Update,
} from './api.generated';
```

**IMPORTANT:** Run `make generate-types` after backend schema changes!

## Mutation Pattern (Create/Update/Delete)

```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { create{Feature} } from '@/lib/api/{feature}';
import { toast } from 'sonner';

function Create{Feature}Form() {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: create{Feature},
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['{feature}s'] });
      toast.success('{Feature} created successfully');
    },
    onError: (error) => {
      toast.error(`Failed to create {feature}: ${error.message}`);
    },
  });

  const handleSubmit = (data: {Feature}Create) => {
    mutation.mutate(data);
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Form fields */}
      <button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? 'Creating...' : 'Create'}
      </button>
    </form>
  );
}
```

## Checklist

Before committing:
- [ ] Page created in correct directory ((protected) or (public))
- [ ] Components created with proper TypeScript types
- [ ] API functions created in lib/api/
- [ ] Types imported from @/types (not api.generated directly)
- [ ] React Query used for data fetching
- [ ] Loading and error states handled
- [ ] Run `npx tsc --noEmit` to check types
- [ ] Run `make lint` to check formatting

## UI Components (shadcn/ui)

Use the shadcn MCP tools to add new UI components:

```
mcp__shadcn__search_items_in_registries - Find components
mcp__shadcn__get_add_command_for_items - Get install command
```

Common components:
- Button, Card, Dialog, Table, Form
- Input, Select, Checkbox, RadioGroup
- Tabs, Accordion, DropdownMenu

## Styling Guidelines

- Use Tailwind CSS classes
- Follow the ornate MTG theme (gold accents, card-like borders)
- Use `cn()` utility for conditional classes
- Responsive: `sm:`, `md:`, `lg:` prefixes

```tsx
import { cn } from '@/lib/utils';

<div className={cn(
  'rounded-lg border p-4',
  isActive && 'border-gold-500 bg-gold-50',
  isDisabled && 'opacity-50 cursor-not-allowed'
)} />
```

## Protected Routes

Protected routes are in `(protected)/` directory:
- Automatically require authentication
- Redirect to login if not authenticated
- Access user via `useAuth()` hook

```tsx
import { useAuth } from '@/components/providers/AuthContext';

function MyComponent() {
  const { user, isAuthenticated, logout } = useAuth();

  if (!isAuthenticated) {
    return null; // Layout handles redirect
  }

  return <div>Hello, {user.username}</div>;
}
```
