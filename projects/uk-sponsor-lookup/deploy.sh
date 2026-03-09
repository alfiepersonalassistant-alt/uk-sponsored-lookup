#!/bin/bash
# Quick deploy script for UK Sponsor Tool
# Run this after making local changes

echo "=== UK Sponsor Tool Deploy Script ==="
echo ""
echo "1. Make sure you've updated the files in:"
echo "   C:\Users\creat\.openclaw\workspace\"
echo ""
echo "2. Files to upload to GitHub:"
echo "   - index.html (if frontend changed)"
echo "   - api.py (if backend changed)"
echo "   - sponsor_lookup.py (if search logic changed)"
echo "   - requirements.txt (if dependencies changed)"
echo ""
echo "3. Go to: https://github.com/alfiepersonalassistant-alt/uk-sponsored-lookup"
echo ""
echo "4. Click 'Add file' → 'Upload files'"
echo ""
echo "5. Select the changed files, commit with message:"
echo "   'Fix: [brief description]'"
echo ""
echo "6. Render will auto-deploy (check https://dashboard.render.com/)"
echo ""
echo "Current status:"
echo "   Live URL: https://uk-sponsored-lookup.onrender.com/"
echo ""
read -p "Press Enter when ready to open GitHub..."
start https://github.com/alfiepersonalassistant-alt/uk-sponsored-lookup
