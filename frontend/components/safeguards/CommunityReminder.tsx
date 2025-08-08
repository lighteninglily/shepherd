'use client';

import { Users, MessageCircle, Calendar } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

type ReminderType = 'community' | 'pastor' | 'group';

interface Reminder {
  type: ReminderType;
  title: string;
  description: string;
  icon: React.ReactNode;
  cta: string;
  ctaLink: string;
}

const reminders: Record<ReminderType, Reminder> = {
  community: {
    type: 'community',
    title: 'Connect with Your Church Family',
    description: 'Consider reaching out to a fellow believer for prayer or fellowship this week.',
    icon: <Users className="h-5 w-5 text-blue-600" />,
    cta: 'Find a Small Group',
    ctaLink: '/groups'
  },
  pastor: {
    type: 'pastor',
    title: 'Talk to a Pastor',
    description: 'Our pastoral team is here to support you. Schedule a time to meet with a pastor.',
    icon: <MessageCircle className="h-5 w-5 text-green-600" />,
    cta: 'Contact a Pastor',
    ctaLink: '/contact/pastoral-care'
  },
  group: {
    type: 'group',
    title: 'Join a Small Group',
    description: 'Experience spiritual growth and community in one of our small groups.',
    icon: <Calendar className="h-5 w-5 text-purple-600" />,
    cta: 'View Groups',
    ctaLink: '/groups'
  }
};

interface CommunityReminderProps {
  type?: ReminderType;
  className?: string;
}

export function CommunityReminder({ 
  type = 'community',
  className = '' 
}: CommunityReminderProps) {
  const reminder = reminders[type];
  
  if (!reminder) return null;

  return (
    <Card className={`border-l-4 border-blue-500 bg-blue-50 dark:bg-blue-900/20 ${className}`}>
      <CardHeader className="p-4 pb-2">
        <div className="flex items-center space-x-2">
          <div className="p-2 rounded-full bg-blue-100 dark:bg-blue-800/50">
            {reminder.icon}
          </div>
          <CardTitle className="text-base font-semibold text-blue-800 dark:text-blue-200">
            {reminder.title}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="p-4 pt-0">
        <p className="text-sm text-blue-700 dark:text-blue-300 mb-3">
          {reminder.description}
        </p>
        <Button 
          variant="outline" 
          size="sm" 
          className="text-blue-700 hover:bg-blue-100 dark:text-blue-200 dark:hover:bg-blue-800/50"
          asChild
        >
          <a href={reminder.ctaLink}>
            {reminder.cta}
          </a>
        </Button>
      </CardContent>
    </Card>
  );
}

export function RandomCommunityReminder() {
  const types: ReminderType[] = ['community', 'pastor', 'group'];
  const randomType = types[Math.floor(Math.random() * types.length)];
  
  return <CommunityReminder type={randomType} />;
}
