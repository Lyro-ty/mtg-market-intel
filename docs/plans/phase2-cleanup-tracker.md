# Phase 2: Visual Overhaul - Cleanup Tracker

Track deprecated code, unused components, and items needing cleanup after migration.

---

## CSS/Styling Changes

| Item | Location | Status | Notes |
|------|----------|--------|-------|
| HSL color format | `globals.css` | Replaced | Changed to RGB format for Ornate Saga |
| `.dark` class selector | `globals.css` | Removed | App is always dark mode now |
| `font-feature-settings` | `globals.css` body | Removed | OpenType ligature settings removed |
| `hsl(var(--...))` in Tailwind | `tailwind.config.js` | Replaced | Changed to `rgb(var(--...))` format |

---

## Components to Remove (After Migration)

| Component | Location | Replacement | Status |
|-----------|----------|-------------|--------|
| `ui/Button.tsx` (old) | `frontend/src/components/ui/` | `@shadcn/button` | Pending |
| `ui/Card.tsx` (old) | `frontend/src/components/ui/` | `@shadcn/card` | Pending |
| `ui/Input.tsx` (old) | `frontend/src/components/ui/` | `@shadcn/input` | Pending |
| `ui/Badge.tsx` (old) | `frontend/src/components/ui/` | `@shadcn/badge` | Pending |
| `ui/Skeleton.tsx` (old) | `frontend/src/components/ui/` | `@shadcn/skeleton` | Pending |
| `ui/Toast.tsx` (old) | `frontend/src/components/ui/` | `@shadcn/sonner` | Pending |
| `ui/Sidebar.tsx` (old) | `frontend/src/components/ui/` | `@shadcn/sidebar` | Pending |

---

## Files to Check/Update

| File | Issue | Action Needed |
|------|-------|---------------|
| Any component using old `Button` | Import path change | Update to shadcn button |
| Any component using old `Card` | Import path change | Update to shadcn card |
| Theme-related context | May have duplicate logic | Consolidate with theme.config.ts |

---

## Dependencies to Review

| Package | Status | Notes |
|---------|--------|-------|
| `tailwindcss-animate` | Added | New dependency for shadcn |
| `class-variance-authority` | Added | For shadcn component variants |
| `clsx` | Added/Kept | For className merging |
| `tailwind-merge` | Added | For Tailwind class deduplication |

---

## Post-Migration Cleanup Tasks

- [ ] Remove old UI components after all pages migrated
- [ ] Audit unused CSS classes in globals.css
- [ ] Remove any unused utility functions
- [ ] Check for orphaned imports
- [ ] Run `npm prune` to remove unused packages
- [ ] Run dead code detection

---

## Notes Log

### 2025-12-28 - Task 2
- Changed color format from HSL to RGB across globals.css and tailwind.config.js
- Removed `.dark` class - app is dark-mode only now
- Removed `font-feature-settings` from body (may want to add back if fonts need ligatures)

---

*Updated during Phase 2 implementation*
