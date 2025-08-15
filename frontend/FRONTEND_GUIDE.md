# Shepherd AI - Frontend Development Guide

## Table of Contents
1. [Project Structure](#project-structure)
2. [Code Style & Best Practices](#code-style--best-practices)
3. [Component Architecture](#component-architecture)
4. [State Management](#state-management)
5. [API Integration](#api-integration)
6. [Styling](#styling)
7. [Testing](#testing)
8. [Performance](#performance)
9. [Accessibility](#accessibility)
10. [Deployment](#deployment)

## Project Structure

```
frontend/
├── app/                    # App router pages (Next.js 13+)
│   ├── layout.tsx          # Root layout
│   ├── page.tsx           # Home page
│   └── (auth)/            # Authentication routes
├── components/
│   ├── ui/                # Reusable UI components
│   ├── layout/            # Layout components
│   └── shared/            # Shared components
├── lib/
│   ├── api/               # API client and utilities
│   └── utils/             # Utility functions
├── public/                # Static assets
├── styles/                # Global styles
└── types/                 # TypeScript type definitions
```

## Code Style & Best Practices

### General Guidelines
- Use TypeScript for type safety
- Follow the [Airbnb React/JSX Style Guide](https://airbnb.io/javascript/react/)
- Use functional components with hooks
- Keep components small and focused
- Use meaningful component and variable names
- Write clean, self-documenting code

### File Naming
- Components: `PascalCase.tsx` (e.g., `UserProfile.tsx`)
- Utilities: `camelCase.ts` (e.g., `formatDate.ts`)
- Test files: `ComponentName.test.tsx`
- Type definitions: `*.d.ts`

## Component Architecture

### Component Types
1. **UI Components**: Reusable, presentational components
2. **Layout Components**: Define page structure
3. **Container Components**: Handle data and state
4. **Page Components**: Top-level route components

### Component Structure
```tsx
import { FC } from 'react';
import PropTypes from 'prop-types';

interface ComponentNameProps {
  // Props interface
}

const ComponentName: FC<ComponentNameProps> = ({ /* destructured props */ }) => {
  // Component logic
  
  return (
    // JSX
  );
};

ComponentName.propTypes = {
  // PropTypes for runtime type checking
};

export default ComponentName;
```

## State Management

### Local State
- Use `useState` for component-level state
- Use `useReducer` for complex state logic

### Global State
- Use React Query for server state
- Use Context API for app-wide state
- Consider Zustand for complex global state

### Data Fetching
- Use React Query for data fetching and caching
- Handle loading and error states
- Implement optimistic updates

## API Integration

### API Client
```typescript
// lib/api/client.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Add auth token if exists
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export default apiClient;
```

### API Hooks
```typescript
// lib/api/hooks/useConversations.ts
import { useQuery } from 'react-query';
import apiClient from '../client';

const fetchConversations = async () => {
  const { data } = await apiClient.get('/conversations');
  return data;
};

export const useConversations = () => {
  return useQuery('conversations', fetchConversations);
};
```

## Styling

### Tailwind CSS
- Use Tailwind's utility classes for styling
- Create reusable component classes with `@apply`
- Follow the design system tokens

### CSS Modules
- Use for component-specific styles
- Follow BEM naming convention
- Keep styles colocated with components

## Testing

### Test Types
- Unit tests for utilities and hooks
- Component tests with React Testing Library
- End-to-end tests with Cypress

### Testing Library Example
```tsx
// components/Button.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import Button from './Button';

describe('Button', () => {
  it('renders button with text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });
});
```

## Performance

### Optimization Techniques
- Code splitting with dynamic imports
- Memoize expensive calculations
- Use `React.memo` for expensive components
- Implement virtualization for long lists

### Performance Monitoring
- Use React DevTools Profiler
- Monitor bundle size with `@next/bundle-analyzer`
- Track Core Web Vitals

## Accessibility

### Best Practices
- Use semantic HTML
- Add proper ARIA attributes
- Ensure keyboard navigation
- Test with screen readers
- Maintain sufficient color contrast

## Deployment

### Build Process
```bash
# Install dependencies
npm install

# Build for production
npm run build

# Start production server
npm start
```

### Environment Variables
```bash
NEXT_PUBLIC_API_BASE_URL=https://api.shepherd.ai
NEXT_PUBLIC_GA_MEASUREMENT_ID=G-XXXXXXXXXX
```

## Development Workflow

1. Create a feature branch
2. Write tests for new features
3. Implement the feature
4. Run linters and tests
5. Create a pull request
6. Get code review
7. Deploy to staging for testing
8. Deploy to production

## Code Review Guidelines
- Check for accessibility issues
- Verify responsive design
- Ensure error handling
- Check for performance optimizations
- Verify test coverage
