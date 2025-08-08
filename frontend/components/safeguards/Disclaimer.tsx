'use client';

import { Info } from 'lucide-react';
import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

export function Disclaimer() {
  const [isVisible, setIsVisible] = useState(false);
  const [isFirstVisit, setIsFirstVisit] = useState(false);

  useEffect(() => {
    const disclaimerAccepted = localStorage.getItem('disclaimerAccepted');
    if (!disclaimerAccepted) {
      setIsFirstVisit(true);
      setIsVisible(true);
    }
  }, []);

  const handleAccept = () => {
    localStorage.setItem('disclaimerAccepted', 'true');
    setIsVisible(false);
    setIsFirstVisit(false);
  };

  if (!isVisible) {
    return (
      <Button 
        variant="ghost" 
        size="sm" 
        className="text-muted-foreground hover:text-foreground"
        onClick={() => setIsVisible(true)}
      >
        <Info className="h-4 w-4 mr-2" />
        Important Information
      </Button>
    );
  }

  return (
    <Alert className="border-l-4 border-amber-500 bg-amber-50 dark:bg-amber-950/20">
      <div className="flex items-start">
        <Info className="h-5 w-5 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
        <div className="ml-3">
          <AlertTitle className="text-amber-800 dark:text-amber-200 font-semibold">
            Important Information
          </AlertTitle>
          <AlertDescription className="text-amber-700 dark:text-amber-300 mt-2 space-y-2">
            <p>
              Shepherd AI is designed to provide spiritual support and guidance within a faith-based context. 
              It is not a substitute for professional medical, psychological, or psychiatric advice, diagnosis, or treatment.
            </p>
            <p>
              <strong>For emergencies or crisis situations, please contact:</strong>
              <ul className="list-disc pl-5 mt-1 space-y-1">
                <li>Emergency Services: 000 (Australia)</li>
                <li>Lifeline: 13 11 14</li>
                <li>Beyond Blue: 1300 22 4636</li>
              </ul>
            </p>
            <p>
              This tool is meant to complement, not replace, your church community and pastoral care relationships.
            </p>
          </AlertDescription>
          {isFirstVisit && (
            <div className="mt-4">
              <Button 
                onClick={handleAccept}
                className="bg-amber-600 hover:bg-amber-700 text-white"
              >
                I Understand
              </Button>
            </div>
          )}
        </div>
      </div>
    </Alert>
  );
}
