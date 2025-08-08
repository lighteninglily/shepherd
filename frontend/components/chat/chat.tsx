'use client';

import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { ScrollArea } from '@/components/ui/scroll-area';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8001';

type Message = {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
};

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Heuristic: detect if the last assistant message is an intake prompt
  const getIntakeInfo = (text: string) => {
    const normalized = (text || '').toLowerCase();
    const isIntake = normalized.includes("let me understand this better") ||
      (normalized.includes('?') && (normalized.includes('are you') || normalized.includes('how long') || normalized.includes('have you')));
    // Count questions by splitting on '?'
    const questionCount = (text.match(/\?/g) || []).length;
    return { isIntake, questionCount };
  };
  const lastAssistant = [...messages].reverse().find(m => m.role === 'assistant');
  const intake = getIntakeInfo(lastAssistant?.content || '');

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: input,
      role: 'user',
      timestamp: new Date(),
    };

    // Add user message to chat
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/v1/chat`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          // In a real app, you'd include an auth token here
          // 'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          messages: updatedMessages.map(({ role, content, timestamp }) => ({
            role,
            content,
            timestamp: timestamp.toISOString()
          })),
          user_id: 'demo-user-1' // Replace with actual user ID from auth
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get response from server');
      }

      const data = await response.json();
      
      const assistantMessage: Message = {
        id: Date.now().toString(),
        content: data.message.content,
        role: 'assistant',
        timestamp: new Date(data.message.timestamp),
      };
      
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      // Add error message to chat
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        content: 'Sorry, I encountered an error. Please try again.',
        role: 'assistant',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Chat with Shepherd</CardTitle>
        <CardDescription>
          Have a conversation with your AI pastoral companion
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ScrollArea className="h-[400px] rounded-lg border p-4">
          <div className="space-y-4">
            {messages.length === 0 ? (
              <div className="flex justify-center items-center h-[300px] text-muted-foreground">
                <p>Start a conversation with Shepherd...</p>
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`flex items-start max-w-[80%] gap-2 ${
                      message.role === 'user' ? 'flex-row-reverse' : 'flex-row'
                    }`}
                  >
                    <Avatar className="h-8 w-8 mt-1">
                      <AvatarFallback>
                        {message.role === 'user' ? 'U' : 'S'}
                      </AvatarFallback>
                    </Avatar>
                    <div
                      className={`rounded-lg px-4 py-2 ${
                        message.role === 'user'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted'
                      }`}
                    >
                      <p className="whitespace-pre-wrap">{message.content}</p>
                      <p className="text-xs opacity-70 mt-1">
                        {message.timestamp.toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </p>
                    </div>
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>
        {intake.isIntake && (
          <div className="text-xs text-muted-foreground flex items-center gap-2">
            <span className="inline-flex items-center rounded-full bg-secondary px-2 py-0.5">
              Context intake{intake.questionCount > 0 ? ` · ${intake.questionCount} question${intake.questionCount > 1 ? 's' : ''}` : ''}
            </span>
            <span>Answer Shepherd’s questions briefly so he can help well.</span>
          </div>
        )}
        
        <form onSubmit={handleSubmit} className="flex space-x-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            disabled={isLoading}
            className="flex-1"
          />
          <Button type="submit" disabled={isLoading || !input.trim()}>
            {isLoading ? 'Sending...' : 'Send'}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
