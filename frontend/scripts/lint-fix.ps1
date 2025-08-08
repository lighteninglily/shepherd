# Run ESLint to find and fix issues
Write-Host "Running ESLint to find and fix issues..."
npx eslint . --fix

# Run Prettier to format code
Write-Host "Running Prettier to format code..."
npx prettier --write .

# Check TypeScript types
Write-Host "Checking TypeScript types..."
npx tsc --noEmit

Write-Host "Linting and formatting complete!"
