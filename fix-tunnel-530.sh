#!/bin/bash
# Fix 530 error - Tunnel origin unregistered

echo "=== Fixing Cloudflare Tunnel 530 Error ==="
echo ""

# 1. Check if frontend is running
echo "1. Checking frontend container..."
if ! docker ps | grep -q frontend; then
    echo "   ✗ Frontend is NOT running!"
    echo "   Starting frontend..."
    docker compose -f docker-compose.production.yml up -d frontend
    sleep 5
else
    echo "   ✓ Frontend is running"
fi
echo ""

# 2. Test localhost:3000
echo "2. Testing localhost:3000..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 | grep -q "200\|301\|302"; then
    echo "   ✓ localhost:3000 is accessible"
    curl -I http://localhost:3000 | head -1
else
    echo "   ✗ localhost:3000 is NOT accessible"
    echo "   Frontend may not be bound correctly"
    echo "   Checking frontend logs..."
    docker logs dualcaster-frontend --tail 20
fi
echo ""

# 3. Check/create config file
echo "3. Checking config file..."
if [ ! -f ~/.cloudflared/config.yml ]; then
    echo "   ✗ Config file missing, creating it..."
    mkdir -p ~/.cloudflared
    cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: 2d42baad-b615-41df-94fd-4f3cca44cd1e
credentials-file: /root/.cloudflared/2d42baad-b615-41df-94fd-4f3cca44cd1e.json

ingress:
  - hostname: dualcasterdeals.com
    service: http://localhost:3000
  - hostname: www.dualcasterdeals.com
    service: http://localhost:3000
  - service: http_status:404
EOF
    echo "   ✓ Config file created"
else
    echo "   ✓ Config file exists"
    echo "   Current config:"
    cat ~/.cloudflared/config.yml
fi
echo ""

# 4. Verify config has ingress rules
echo "4. Verifying ingress rules..."
if grep -q "ingress:" ~/.cloudflared/config.yml && grep -q "dualcasterdeals.com" ~/.cloudflared/config.yml; then
    echo "   ✓ Ingress rules found in config"
else
    echo "   ✗ Ingress rules missing or incorrect"
    echo "   Updating config..."
    cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: 2d42baad-b615-41df-94fd-4f3cca44cd1e
credentials-file: /root/.cloudflared/2d42baad-b615-41df-94fd-4f3cca44cd1e.json

ingress:
  - hostname: dualcasterdeals.com
    service: http://localhost:3000
  - hostname: www.dualcasterdeals.com
    service: http://localhost:3000
  - service: http_status:404
EOF
fi
echo ""

echo "=== Next Steps ==="
echo ""
echo "1. Make sure tunnel is running with config:"
echo "   cloudflared tunnel --config ~/.cloudflared/config.yml run dualcaster"
echo ""
echo "2. If tunnel is already running, stop it (Ctrl+C) and restart with config"
echo ""
echo "3. Verify frontend is accessible:"
echo "   curl http://localhost:3000"
echo ""



