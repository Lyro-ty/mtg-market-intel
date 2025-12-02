#!/bin/bash
# Script to check and fix Cloudflare Tunnel setup

echo "=== Checking Cloudflare Tunnel Setup ==="
echo ""

# 1. Check if config file exists
echo "1. Checking config file..."
if [ -f ~/.cloudflared/config.yml ]; then
    echo "   ✓ Config file exists at ~/.cloudflared/config.yml"
    echo "   Contents:"
    cat ~/.cloudflared/config.yml
    echo ""
else
    echo "   ✗ Config file NOT found at ~/.cloudflared/config.yml"
    echo ""
fi

# 2. Check if frontend is running
echo "2. Checking if frontend container is running..."
if docker ps | grep -q frontend; then
    echo "   ✓ Frontend container is running"
    docker ps | grep frontend
else
    echo "   ✗ Frontend container is NOT running"
    echo "   Run: docker compose -f docker-compose.production.yml up -d"
fi
echo ""

# 3. Check if localhost:3000 is accessible
echo "3. Testing localhost:3000..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 | grep -q "200\|301\|302"; then
    echo "   ✓ localhost:3000 is accessible"
else
    echo "   ✗ localhost:3000 is NOT accessible"
    echo "   Frontend may not be running or not bound to port 3000"
fi
echo ""

# 4. Check tunnel list
echo "4. Checking tunnel list..."
cloudflared tunnel list
echo ""

echo "=== Setup Instructions ==="
echo ""
echo "If config file is missing or incorrect, create it with:"
echo ""
echo "mkdir -p ~/.cloudflared"
echo "cat > ~/.cloudflared/config.yml << 'EOF'"
echo "tunnel: 2d42baad-b615-41df-94fd-4f3cca44cd1e"
echo "credentials-file: /root/.cloudflared/2d42baad-b615-41df-94fd-4f3cca44cd1e.json"
echo ""
echo "ingress:"
echo "  - hostname: dualcasterdeals.com"
echo "    service: http://localhost:3000"
echo "  - hostname: www.dualcasterdeals.com"
echo "    service: http://localhost:3000"
echo "  - service: http_status:404"
echo "EOF"
echo ""


