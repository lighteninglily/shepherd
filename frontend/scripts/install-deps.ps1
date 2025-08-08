# Install Node.js dependencies
Write-Host "Installing Node.js dependencies..."
npm install

# Install Python dependencies
Write-Host "Installing Python dependencies..."
pip install -r ..\backend\requirements.txt

Write-Host "Installation complete!"
