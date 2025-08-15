'use client';

import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { ScrollArea } from '@/components/ui/scroll-area';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
const DEBUG_PANEL = (process.env.NEXT_PUBLIC_DEBUG_PANEL || '').toLowerCase() === 'true';

type Message = {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
  metadata?: any;
};

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [debugOpen, setDebugOpen] = useState<Record<string, boolean>>({});

  const toggleDebug = (id: string) => {
    setDebugOpen((prev) => ({ ...prev, [id]: !prev[id] }));
  };

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

  // Quick replies to encourage deeper sharing (friend-like tone)
  const quickReplies: string[] = [
    'That sounds really hard.',
    'Can you say more about how that felt?',
    'What happened just before that?'
  ];

  // Detect if the assistant is asking about faith status
  const isFaithQuestion = !!(lastAssistant && /are you (a )?follower of jesus|are you (a )?christian|exploring faith/i.test(lastAssistant.content));
  const faithReplies: string[] = [
    "I'm a follower of Jesus",
    "I'm exploring faith",
    "I'm not Christian",
  ];

  // Detect if the assistant is emphasizing identity in Christ (heuristic)
  const isIdentityEmphasis = !!(lastAssistant && (
    /identity in christ|child of god|beloved (?:in|by) god|your identity (?:is|in)/i.test(lastAssistant.content) ||
    /(2 Corinthians 5:17|Galatians 2:20|Romans 8:38-39|Ephesians 3:17-19|1 John 3:1)/i.test(lastAssistant.content)
  ));
  const identityReplies: string[] = [
    'Can you help me anchor my identity in Christ?',
    'Could you share a short verse about identity?',
    'How might I bring this to Jesus this week?'
  ];

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
      const bodyPayload: any = {
        messages: updatedMessages.map(({ role, content, timestamp }) => ({
          role,
          content,
          timestamp: timestamp.toISOString()
        })),
        user_id: 'demo-user-1', // Replace with actual user ID from auth
      };
      if (conversationId) {
        bodyPayload.conversation_id = conversationId;
      }

      const response = await fetch(`${API_BASE}/api/v1/chat`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          // In a real app, you'd include an auth token here
          // 'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(bodyPayload),
      });

      if (!response.ok) {
        throw new Error('Failed to get response from server');
      }

      const data = await response.json();
      if (data?.conversation_id && data.conversation_id !== conversationId) {
        setConversationId(data.conversation_id);
      }
      
      const assistantMessage: Message = {
        id: Date.now().toString(),
        content: data.message.content,
        role: 'assistant',
        timestamp: new Date(data.message.timestamp),
        metadata: data?.message?.metadata || {},
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
                      {message.role === 'assistant' && message.metadata && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {/* Book attribution badges */}
                          {Array.isArray(message.metadata.book_attributions) && message.metadata.book_attributions.length > 0 && (
                            <div className="flex flex-wrap gap-2 items-center">
                              {message.metadata.book_attributions.map((b: any, idx: number) => (
                                <span key={`${b?.key || b?.pretty || idx}`} className="inline-flex items-center rounded-full bg-secondary px-2 py-0.5 text-xs">
                                  Resource · {b?.pretty || 'Unknown'}{b?.author ? ` by ${b.author}` : ''}
                                </span>
                              ))}
                            </div>
                          )}
                          {/* Using insights subtly when resources are gated */}
                          {message.metadata.used_book_insights && message.metadata.allow_books === false && (
                            <span className="inline-flex items-center rounded-full bg-muted-foreground/10 px-2 py-0.5 text-xs">
                              Using book insights
                            </span>
                          )}
                          {/* Jesus-centered emphasis tag */}
                          {message.metadata.rooted_in_jesus_emphasis && (
                            <span className="inline-flex items-center rounded-full bg-secondary/70 px-2 py-0.5 text-xs">
                              Jesus-centered
                            </span>
                          )}
                          {/* Conversation phase and gating */}
                          {message.metadata.phase && (
                            <span className="inline-flex items-center rounded-full bg-muted-foreground/10 px-2 py-0.5 text-xs">
                              Phase · {String(message.metadata.phase)}
                            </span>
                          )}
                          {typeof message.metadata.allow_books !== 'undefined' && (
                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs ${message.metadata.allow_books ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                              {message.metadata.allow_books ? 'Resources allowed' : 'Resources gated'}
                            </span>
                          )}
                          {message.metadata.safety_flag_this_turn && (
                            <span className="inline-flex items-center rounded-full bg-red-100 text-red-800 px-2 py-0.5 text-xs">
                              Safety check
                            </span>
                          )}
                        </div>
                      )}
                      {/* Debug Panel Toggle and Content */}
                      {message.role === 'assistant' && DEBUG_PANEL && message.metadata && (
                        <div className="mt-2">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => toggleDebug(message.id)}
                          >
                            {debugOpen[message.id] ? 'Hide details' : 'Details'}
                          </Button>
                          {debugOpen[message.id] && (
                            <div className="mt-2 rounded-md border bg-background p-2 text-[11px] space-y-1">
                              <div className="flex flex-wrap gap-2">
                                {typeof message.metadata.advice_intent !== 'undefined' && (
                                  <span className="inline-flex items-center rounded bg-muted px-2 py-0.5">Advice intent · {String(message.metadata.advice_intent)}</span>
                                )}
                                {message.metadata.gate_reason && (
                                  <span className="inline-flex items-center rounded bg-muted px-2 py-0.5">Gate · {String(message.metadata.gate_reason)}</span>
                                )}
                                {message.metadata.book_selection_reason && (
                                  <span className="inline-flex items-center rounded bg-muted px-2 py-0.5">Book reason · {String(message.metadata.book_selection_reason)}</span>
                                )}
                                {typeof message.metadata.asked_question !== 'undefined' && (
                                  <span className="inline-flex items-center rounded bg-muted px-2 py-0.5">Asked question · {String(message.metadata.asked_question)}</span>
                                )}
                                {typeof message.metadata.rooted_in_jesus_emphasis !== 'undefined' && (
                                  <span className="inline-flex items-center rounded bg-muted px-2 py-0.5">Jesus emphasis · {String(message.metadata.rooted_in_jesus_emphasis)}</span>
                                )}
                                {message.metadata.faith_branch && (
                                  <span className="inline-flex items-center rounded bg-muted px-2 py-0.5">Faith branch · {String(message.metadata.faith_branch)}</span>
                                )}
                                {typeof message.metadata.allow_books !== 'undefined' && (
                                  <span className="inline-flex items-center rounded bg-muted px-2 py-0.5">Allow books · {String(message.metadata.allow_books)}</span>
                                )}
                                {typeof message.metadata.used_book_insights !== 'undefined' && (
                                  <span className="inline-flex items-center rounded bg-muted px-2 py-0.5">Using insights · {String(message.metadata.used_book_insights)}</span>
                                )}
                                {message.metadata.phase && (
                                  <span className="inline-flex items-center rounded bg-muted px-2 py-0.5">Phase · {String(message.metadata.phase)}</span>
                                )}
                                {message.metadata.topic && (
                                  <span className="inline-flex items-center rounded bg-muted px-2 py-0.5">Topic · {String(message.metadata.topic)}</span>
                                )}
                                {typeof message.metadata.topic_confidence !== 'undefined' && (
                                  <span className="inline-flex items-center rounded bg-muted px-2 py-0.5">Topic conf · {String(message.metadata.topic_confidence)}</span>
                                )}
                              </div>
                              {(Array.isArray(message.metadata.scrubbed_books) && message.metadata.scrubbed_books.length > 0) && (
                                <div>Scrubbed: {message.metadata.scrubbed_books.join(', ')}</div>
                              )}
                              <details>
                                <summary className="cursor-pointer select-none text-muted-foreground">Raw metadata</summary>
                                <pre className="whitespace-pre-wrap break-words text-[11px] leading-4">{JSON.stringify(message.metadata, null, 2)}</pre>
                              </details>
                            </div>
                          )}
                        </div>
                      )}
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
        {/* Quick reply chips */}
        <div className="flex flex-wrap gap-2">
          {quickReplies.map((qr) => (
            <Button
              key={qr}
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setInput((prev) => (prev ? `${prev} ${qr}` : qr))}
              disabled={isLoading}
            >
              {qr}
            </Button>
          ))}
        </div>
        {/* Faith quick replies (only shown when relevant) */}
        {isFaithQuestion && (
          <div className="flex flex-wrap gap-2">
            {faithReplies.map((qr) => (
              <Button
                key={qr}
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setInput((prev) => (prev ? `${prev} ${qr}` : qr))}
                disabled={isLoading}
              >
                {qr}
              </Button>
            ))}
          </div>
        )}
        {/* Identity-in-Christ quick replies (only shown when relevant) */}
        {isIdentityEmphasis && (
          <div className="flex flex-wrap gap-2">
            {identityReplies.map((qr) => (
              <Button
                key={qr}
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setInput((prev) => (prev ? `${prev} ${qr}` : qr))}
                disabled={isLoading}
              >
                {qr}
              </Button>
            ))}
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
