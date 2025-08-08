"use client"

import { User } from "lucide-react"
import { SignInButton, SignUpButton, SignedIn, SignedOut, UserButton } from "@clerk/nextjs"
import { Button } from "@/components/ui/button"

export function UserAuthButton() {
  return (
    <div className="flex items-center space-x-2">
      <SignedIn>
        <UserButton afterSignOutUrl="/" />
      </SignedIn>
      <SignedOut>
        <div className="flex space-x-2">
          <SignInButton mode="modal">
            <Button variant="outline" size="sm">
              Sign In
            </Button>
          </SignInButton>
          <SignUpButton mode="modal">
            <Button size="sm">Sign Up</Button>
          </SignUpButton>
        </div>
      </SignedOut>
    </div>
  )
}
