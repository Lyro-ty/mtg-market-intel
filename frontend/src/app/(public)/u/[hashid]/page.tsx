'use client';

import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { MapPin, Calendar, Package } from 'lucide-react';
import { fetchApi } from '@/lib/api';

interface PublicProfile {
  username: string;
  display_name: string | null;
  bio: string | null;
  location: string | null;
  avatar_url: string | null;
  created_at: string;
  hashid: string;
  cards_for_trade: number;
}

export default function PublicProfilePage() {
  const params = useParams();
  const hashid = params.hashid as string;

  const { data: profile, isLoading, error } = useQuery<PublicProfile>({
    queryKey: ['public-profile', hashid],
    queryFn: () => fetchApi(`/profile/public/${hashid}`),
    enabled: !!hashid,
  });

  if (isLoading) {
    return (
      <div className="container mx-auto py-8 max-w-2xl">
        <Card>
          <CardHeader className="flex flex-row items-center gap-4">
            <Skeleton className="h-20 w-20 rounded-full" />
            <div className="space-y-2">
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-4 w-32" />
            </div>
          </CardHeader>
          <CardContent>
            <Skeleton className="h-20 w-full" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="container mx-auto py-8 max-w-2xl">
        <Card>
          <CardContent className="py-12 text-center">
            <h2 className="text-xl font-semibold text-muted-foreground">
              User not found
            </h2>
            <p className="text-sm text-muted-foreground mt-2">
              This profile may have been removed or the link is invalid.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const displayName = profile.display_name || profile.username;
  const initials = displayName.slice(0, 2).toUpperCase();
  const memberSince = new Date(profile.created_at).toLocaleDateString('en-US', {
    month: 'long',
    year: 'numeric',
  });

  return (
    <div className="container mx-auto py-8 max-w-2xl">
      <Card>
        <CardHeader>
          <div className="flex items-start gap-6">
            <Avatar className="h-24 w-24">
              <AvatarImage src={profile.avatar_url || undefined} alt={displayName} />
              <AvatarFallback className="text-2xl">{initials}</AvatarFallback>
            </Avatar>

            <div className="flex-1 space-y-2">
              <CardTitle className="text-2xl">{displayName}</CardTitle>

              <p className="text-muted-foreground">@{profile.username}</p>

              <div className="flex flex-wrap gap-3 mt-3">
                {profile.location && (
                  <div className="flex items-center gap-1 text-sm text-muted-foreground">
                    <MapPin className="h-4 w-4" />
                    <span>{profile.location}</span>
                  </div>
                )}

                <div className="flex items-center gap-1 text-sm text-muted-foreground">
                  <Calendar className="h-4 w-4" />
                  <span>Member since {memberSince}</span>
                </div>
              </div>
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-6">
          {profile.bio && (
            <div>
              <h3 className="font-medium mb-2">About</h3>
              <p className="text-muted-foreground">{profile.bio}</p>
            </div>
          )}

          <div className="border-t pt-4">
            <h3 className="font-medium mb-3">Trading</h3>
            <div className="flex items-center gap-2">
              <Package className="h-5 w-5 text-muted-foreground" />
              <span className="text-lg font-semibold">{profile.cards_for_trade}</span>
              <span className="text-muted-foreground">cards available for trade</span>
            </div>

            {profile.cards_for_trade > 0 && (
              <Badge variant="secondary" className="mt-3">
                Open to trades
              </Badge>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
