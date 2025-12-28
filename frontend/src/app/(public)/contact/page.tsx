'use client';

import React, { useState } from 'react';
import {
  Mail,
  MessageSquare,
  Send,
  Github,
  Twitter,
  HelpCircle,
  Bug,
  Lightbulb,
  CheckCircle,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { PageHeader } from '@/components/ornate/page-header';
import { cn } from '@/lib/utils';

const contactReasons = [
  { id: 'general', label: 'General Inquiry', icon: MessageSquare },
  { id: 'support', label: 'Technical Support', icon: HelpCircle },
  { id: 'bug', label: 'Report a Bug', icon: Bug },
  { id: 'feature', label: 'Feature Request', icon: Lightbulb },
];

export default function ContactPage() {
  const [selectedReason, setSelectedReason] = useState('general');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // In production, this would send to backend
    setSubmitted(true);
  };

  if (submitted) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Card className="max-w-md mx-auto glow-accent">
          <CardContent className="p-8 text-center">
            <div className="w-16 h-16 rounded-full bg-[rgb(var(--success))]/20 flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="w-8 h-8 text-[rgb(var(--success))]" />
            </div>
            <h2 className="font-display text-2xl text-foreground mb-2">Message Sent!</h2>
            <p className="text-muted-foreground mb-6">
              Thank you for reaching out. We&apos;ll get back to you within 24-48 hours.
            </p>
            <Button
              variant="secondary"
              onClick={() => setSubmitted(false)}
              className="glow-accent"
            >
              Send Another Message
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 space-y-8">
      <PageHeader
        title="Contact Us"
        subtitle="We'd love to hear from you"
      />

      <div className="grid md:grid-cols-3 gap-8">
        {/* Contact Form */}
        <div className="md:col-span-2">
          <Card className="glow-accent">
            <CardHeader>
              <CardTitle>Send a Message</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-6">
                {/* Reason Selection */}
                <div className="space-y-2">
                  <Label>What can we help you with?</Label>
                  <div className="grid grid-cols-2 gap-2">
                    {contactReasons.map((reason) => {
                      const Icon = reason.icon;
                      return (
                        <button
                          key={reason.id}
                          type="button"
                          onClick={() => setSelectedReason(reason.id)}
                          className={cn(
                            'flex items-center gap-2 p-3 rounded-lg border transition-all text-left',
                            selectedReason === reason.id
                              ? 'border-[rgb(var(--accent))] bg-[rgb(var(--accent))]/10 text-foreground'
                              : 'border-border bg-secondary/50 text-muted-foreground hover:border-[rgb(var(--accent))]/50'
                          )}
                        >
                          <Icon className={cn(
                            'w-5 h-5',
                            selectedReason === reason.id ? 'text-[rgb(var(--accent))]' : ''
                          )} />
                          <span className="text-sm font-medium">{reason.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Name & Email */}
                <div className="grid md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="name">Name</Label>
                    <Input id="name" placeholder="Your name" required />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input id="email" type="email" placeholder="you@example.com" required />
                  </div>
                </div>

                {/* Subject */}
                <div className="space-y-2">
                  <Label htmlFor="subject">Subject</Label>
                  <Input id="subject" placeholder="Brief description of your inquiry" required />
                </div>

                {/* Message */}
                <div className="space-y-2">
                  <Label htmlFor="message">Message</Label>
                  <textarea
                    id="message"
                    rows={5}
                    placeholder="Tell us more..."
                    required
                    className="w-full px-3 py-2 rounded-lg border border-border bg-card text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-[rgb(var(--accent))]/50 resize-none"
                  />
                </div>

                <Button type="submit" className="w-full gradient-arcane text-white glow-accent">
                  <Send className="w-4 h-4 mr-2" />
                  Send Message
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Direct Contact */}
          <Card className="glow-accent">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mail className="w-5 h-5 text-[rgb(var(--accent))]" />
                Direct Contact
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm text-muted-foreground mb-1">Email</p>
                <a
                  href="mailto:support@dualcasterdeals.com"
                  className="text-[rgb(var(--accent))] hover:underline"
                >
                  support@dualcasterdeals.com
                </a>
              </div>
              <div>
                <p className="text-sm text-muted-foreground mb-1">Response Time</p>
                <p className="text-foreground">Within 24-48 hours</p>
              </div>
            </CardContent>
          </Card>

          {/* Social Links */}
          <Card className="glow-accent">
            <CardHeader>
              <CardTitle>Connect With Us</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <a
                href="https://github.com/dualcasterdeals"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-3 rounded-lg bg-secondary/50 hover:bg-secondary transition-colors"
              >
                <Github className="w-5 h-5 text-foreground" />
                <div>
                  <p className="font-medium text-foreground">GitHub</p>
                  <p className="text-xs text-muted-foreground">Report issues & contribute</p>
                </div>
              </a>
              <a
                href="https://twitter.com/dualcasterdeals"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-3 rounded-lg bg-secondary/50 hover:bg-secondary transition-colors"
              >
                <Twitter className="w-5 h-5 text-[rgb(var(--info))]" />
                <div>
                  <p className="font-medium text-foreground">Twitter</p>
                  <p className="text-xs text-muted-foreground">Updates & announcements</p>
                </div>
              </a>
            </CardContent>
          </Card>

          {/* FAQ Link */}
          <Card className="glow-accent bg-gradient-to-br from-[rgb(var(--accent))]/10 to-transparent">
            <CardContent className="p-6 text-center">
              <HelpCircle className="w-8 h-8 mx-auto text-[rgb(var(--accent))] mb-3" />
              <h3 className="font-heading font-medium text-foreground mb-2">
                Check our FAQ first
              </h3>
              <p className="text-sm text-muted-foreground mb-4">
                Many common questions are already answered.
              </p>
              <Button variant="secondary" size="sm" asChild>
                <a href="/help">View FAQ</a>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
