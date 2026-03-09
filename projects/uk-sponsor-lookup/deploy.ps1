# Quick deploy script for UK Sponsor Tool
# Run this after making local changes

Write-Host "=== UK Sponsor Tool Deploy Script ===" -ForegroundColor Green
Write-Host ""
Write-Host "1. Files to upload to GitHub:" -ForegroundColor Yellow
Write-Host "   - index.html (if frontend changed)"
Write-Host "   - api.py (if backend changed)"  
Write-Host "   - sponsor_lookup.py (if search logic changed)"
Write-Host ""
Write-Host "2. Go to GitHub repo..." -ForegroundColor Yellow
Start-Process "https://github.com/alfiepersonalassistant-alt/uk-sponsored-lookup"
Write-Host ""
Write-Host "3. Click 'Add file' → 'Upload files'" -ForegroundColor Yellow
Write-Host ""
Write-Host "4. Select changed files and commit" -ForegroundColor Yellow
Write-Host ""
Write-Host "5. Render auto-deploys (check dashboard)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Live URL: https://uk-sponsored-lookup.onrender.com/" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to open GitHub"
