# Fix Frontend Connection Issue

## Problem
Cloudflared error: `dial tcp 127.0.0.1:3000: connect: connection refused`

This means cloudflared can't reach the frontend on port 3000.

## Quick Diagnosis

### 1. Check if Frontend Container is Running

```bash
docker compose -f docker-compose.production.yml ps frontend
```

**Expected:** Should show "Up" status

### 2. Check Frontend Logs

```bash
docker logs dualcaster-frontend --tail 100
```

**Look for:**
- Build errors
- Startup errors
- Port binding errors
- "Server ready" or "Listening on" messages

### 3. Test Frontend Directly

```bash
# From host machine
curl http://localhost:3000

# Or check if port is listening
netstat -tuln | grep 3000
# Or
ss -tuln | grep 3000
```

**Expected:** Should return HTML or HTTP 200

### 4. Check Frontend Container Ports

```bash
docker port dualcaster-frontend
```

**Expected:** Should show `3000/tcp -> 0.0.0.0:3000`

## Common Fixes

### Fix 1: Frontend Container Not Running

If frontend is not running:

```bash
docker compose -f docker-compose.production.yml up -d frontend
```

### Fix 2: Frontend Build Failed

If frontend failed to build:

```bash
# Rebuild frontend
docker compose -f docker-compose.production.yml build --no-cache frontend

# Start it
docker compose -f docker-compose.production.yml up -d frontend
```

### Fix 3: Port Already in Use

If port 3000 is already in use:

```bash
# Find what's using port 3000
lsof -i :3000
# Or
netstat -tuln | grep 3000

# Kill the process or change the port mapping in docker-compose.production.yml
```

### Fix 4: Frontend Not Binding to 0.0.0.0

Check if frontend is configured to listen on all interfaces. The Dockerfile should have:

```dockerfile
ENV HOSTNAME "0.0.0.0"
ENV PORT 3000
```

### Fix 5: Network Issues

Verify frontend is on the correct network:

```bash
docker network inspect mtg-market-intel_dualcaster-network | grep frontend
```

## Verification

After fixing, verify:

1. **Frontend is running:**
   ```bash
   docker compose -f docker-compose.production.yml ps frontend
   ```

2. **Frontend is accessible:**
   ```bash
   curl http://localhost:3000
   # Should return HTML
   ```

3. **Cloudflared can connect:**
   ```bash
   # Check cloudflared logs
   # Should no longer see "connection refused" errors
   ```

## Quick Restart All Services

If unsure, restart everything:

```bash
docker compose -f docker-compose.production.yml down
docker compose -f docker-compose.production.yml up -d
```

Wait for all services to be healthy, then test:

```bash
curl http://localhost:3000
curl http://localhost:8000/api/health
```

