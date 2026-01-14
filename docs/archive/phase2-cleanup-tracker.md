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
| `ui/Button.tsx` (old) | `frontend/src/components/ui/` | `@shadcn/button` | **DONE** (Task 4) |
| `ui/Card.tsx` (old) | `frontend/src/components/ui/` | `@shadcn/card` | **DONE** (Task 4) |
| `ui/Input.tsx` (old) | `frontend/src/components/ui/` | `@shadcn/input` | **DONE** (Task 4) |
| `ui/Badge.tsx` (old) | `frontend/src/components/ui/` | `@shadcn/badge` | **DONE** (Task 4) |
| `ui/Skeleton.tsx` (old) | `frontend/src/components/ui/` | `@shadcn/skeleton` | **DONE** (Task 4) |
| `ui/Toast.tsx` (old) | `frontend/src/components/ui/` | Custom ToastContext | **KEEPING** - Still in use with custom implementation |
| `ui/Sidebar.tsx` (old) | `frontend/src/components/ui/` | `@shadcn/sidebar` | **DONE** - Renamed to AppSidebar.tsx (Task 6) |
| `ui/AppSidebar.tsx` (old) | `frontend/src/components/ui/` | `layout/app-sidebar.tsx` | **DONE** - Removed (2025-12-28) |

---

## Components Retained (Not in shadcn)

| Component | Location | Notes |
|-----------|----------|-------|
| `ErrorBoundary.tsx` | `frontend/src/components/ui/` | React error boundary - keep |
| `ErrorDisplay.tsx` | `frontend/src/components/ui/` | Error UI - keep |
| `Loading.tsx` | `frontend/src/components/ui/` | Loading spinner - keep |
| `ThemePicker.tsx` | `frontend/src/components/ui/` | Mana theme selector - keep |
| ~~`AppSidebar.tsx`~~ | ~~`frontend/src/components/ui/`~~ | **REMOVED** - Replaced by layout/app-sidebar.tsx |

---

## Files to Check/Update

| File | Issue | Action Needed |
|------|-------|---------------|
| ~~Any component using old `Button`~~ | ~~Import path change~~ | **DONE** - Updated to lowercase |
| ~~Any component using old `Card`~~ | ~~Import path change~~ | **DONE** - Updated to lowercase |
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

- [x] Remove old UI components after all pages migrated (2025-12-28)
- [ ] Audit unused CSS classes in globals.css
- [ ] Remove any unused utility functions
- [x] Check for orphaned imports (2025-12-28 - fixed Badge test)
- [x] Run `npm prune` to remove unused packages (2025-12-28 - no unused packages)
- [ ] Run dead code detection

---

## Notes Log

### 2025-12-28 - Task 2
- Changed color format from HSL to RGB across globals.css and tailwind.config.js
- Removed `.dark` class - app is dark-mode only now
- Removed `font-feature-settings` from body (may want to add back if fonts need ligatures)

### 2025-12-28 - Task 4
- Installed 15 shadcn components: button, card, input, label, badge, skeleton, dialog, dropdown-menu, select, tabs, table, tooltip, avatar, separator, scroll-area
- Removed old custom components: Badge.tsx, Button.tsx, Card.tsx, Input.tsx, Skeleton.tsx
- Updated all imports from PascalCase to lowercase paths (37 files)
- Added backward-compatible variants to shadcn components (primary/danger button, success/warning badge, interactive card)
- Migrated composite skeletons (CardSkeleton, ChartSkeleton, etc.) to skeleton.tsx

---

### 2025-12-28 - Final Cleanup
- Removed old `AppSidebar.tsx` from `ui/` directory (replaced by `layout/app-sidebar.tsx`)
- Fixed `Badge.test.tsx` import path from uppercase `Badge` to lowercase `badge`
- Updated test assertions to match new shadcn badge implementation
- Ran `npm prune` - no unused packages found
- Verified Next.js build passes (22 static pages generated)
- Keeping `Toast.tsx` - still in use with custom `ToastContext` implementation

*Updated during Phase 2 implementation*
