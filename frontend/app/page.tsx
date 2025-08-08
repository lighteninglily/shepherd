'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ThemeToggle } from '@/components/theme-toggle';
import { Chat } from '@/components/chat/chat';

export default function Home() {
  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <header className="border-b">
        <div className="container flex items-center justify-between h-16 px-4">
          <div className="flex items-center space-x-2
          ">
            <h1 className="text-xl font-bold">Shepherd AI</h1>
          </div>
          <div className="flex items-center space-x-4">
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 py-8">
        <div className="container max-w-4xl mx-auto px-4">
          <Tabs defaultValue="chat" className="w-full">
            <TabsList className="grid w-full grid-cols-3 max-w-md mx-auto mb-8">
              <TabsTrigger value="chat">Chat</TabsTrigger>
              <TabsTrigger value="prayer">Prayer Journal</TabsTrigger>
              <TabsTrigger value="bible">Bible Study</TabsTrigger>
            </TabsList>

            {/* Chat Tab */}
            <TabsContent value="chat">
              <Chat />
            </TabsContent>

            {/* Prayer Journal Tab */}
            <TabsContent value="prayer">
              <Card>
                <CardHeader>
                  <CardTitle>Prayer Journal</CardTitle>
                  <CardDescription>
                    Record your prayers and reflections
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="prayer-title">Title</Label>
                    <Input id="prayer-title" placeholder="Enter a title for your prayer" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="prayer-content">Your Prayer</Label>
                    <div className="h-64 rounded-md border">
                      <textarea
                        id="prayer-content"
                        className="w-full h-full p-2 focus:outline-none resize-none"
                        placeholder="Write your prayer here..."
                      />
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <Button>Save Prayer</Button>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Bible Study Tab */}
            <TabsContent value="bible">
              <Card>
                <CardHeader>
                  <CardTitle>Bible Study</CardTitle>
                  <CardDescription>
                    Read and study the Bible with Shepherd
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="book">Book</Label>
                      <select
                        id="book"
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <option value="">Select a book</option>
                        <option value="genesis">Genesis</option>
                        <option value="exodus">Exodus</option>
                        {/* Add more books */}
                      </select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="chapter">Chapter</Label>
                      <Input id="chapter" type="number" min="1" placeholder="1" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="verse">Verse (optional)</Label>
                      <Input id="verse" type="number" min="1" placeholder="e.g. 16" />
                    </div>
                  </div>
                  <div className="h-64 rounded-lg border p-4 overflow-y-auto">
                    <p className="text-muted-foreground italic">Select a passage to begin reading...</p>
                  </div>
                  <div className="flex justify-end">
                    <Button>Read Passage</Button>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t py-6">
        <div className="container flex flex-col items-center justify-between gap-4 md:flex-row px-4">
          <p className="text-sm text-muted-foreground">
            Shepherd AI - A pastoral companion for your spiritual journey
          </p>
          <p className="text-sm text-muted-foreground">
            © {new Date().getFullYear()} The Way Church. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  )
}
