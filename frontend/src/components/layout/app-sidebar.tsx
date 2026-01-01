'use client';

import * as React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
} from '@/components/ui/sidebar';
import { NavMain } from './nav-main';
import { NavUser } from './nav-user';
import {
  mainNavItems,
  collectionNavItems,
  insightsNavItems,
  storeNavItems,
  bottomNavItems,
} from '@/config/navigation.config';
import { useAuth } from '@/contexts/AuthContext';

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { user } = useAuth();

  // Filter items based on auth
  const filterItems = (items: typeof mainNavItems) =>
    items.filter(item => !item.requiresAuth || user);

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <Link href={user ? '/dashboard' : '/'} className="flex items-center gap-2 px-2 py-1">
          <Image
            src="/logo.png"
            alt="Dualcaster Deals"
            width={32}
            height={32}
            className="rounded-lg"
          />
          <span className="font-heading text-lg font-semibold group-data-[collapsible=icon]:hidden">
            Dualcaster
          </span>
        </Link>
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={filterItems(mainNavItems)} />
        {user && (
          <>
            <NavMain items={filterItems(collectionNavItems)} label="Collection" />
            <NavMain items={filterItems(insightsNavItems)} label="Insights" />
            <NavMain items={filterItems(storeNavItems)} label="Store" />
          </>
        )}
        <NavMain items={filterItems(bottomNavItems)} label="Support" />
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
