# Troubleshooting Bad Gateway Error

## Quick Diagnosis

A "Bad Gateway" (502) error typically means:
- Frontend can't reach the backend
- Backend is not running or unhealthy
- Network connectivity issues
- Backend is crashing on startup

## Step-by-Step Troubleshooting

### 1. Check Container Status

```bash
docker compose -f docker-compose.production.yml ps
```

**Expected:** All containers should show "Up" status. If backend shows "Restarting" or "Exited", it's failing.

### 2. Check Backend Logs

```bash
docker logs dualcaster-backend --tail 100
```

**Look for:**
- Syntax errors (we just fixed parameter ordering)
- Import errors
- Database connection errors
- Application startup errors

### 3. Check Backend Health Directly

```bash
# From inside the backend container
docker exec dualcaster-backend curl -f http://localhost:8000/api/health

# Or from host (if port is exposed)
curl http://localhost:8000/api/health
```

**Expected:** Should return JSON with `{"status": "healthy", ...}`

### 4. Check Frontend Logs

```bash
docker logs dualcaster-frontend --tail 100
```

**Look for:**
- Build errors
- Runtime errors
- Connection errors to backend

### 5. Verify Network Connectivity

```bash
# From frontend container, test backend connectivity
docker exec dualcaster-frontend wget -O- http://backend:8000/api/health

# Or using curl if available
docker exec dualcaster-frontend curl http://backend:8000/api/health
```

**Expected:** Should return health check JSON

### 6. Check Backend Startup

The backend might be failing during startup. Check if it's actually running:

```bash
docker exec dualcaster-backend ps aux | grep uvicorn
```

**Expected:** Should see uvicorn process running

## Common Issues and Fixes

### Issue 1: Backend Syntax Error (Just Fixed)

**Symptom:** Backend container keeps restarting, logs show syntax errors

**Fix:** We just fixed the parameter ordering issue. Restart the backend:

```bash
docker compose -f docker-compose.production.yml restart backend
```

### Issue 2: Backend Not Starting

**Symptom:** Backend container exits immediately

**Check:**
```bash
docker logs dualcaster-backend --tail 200
```

**Common causes:**
- Database connection failure
- Missing environment variables
- Import errors
- Port already in use

### Issue 3: Health Check Failing

**Symptom:** Backend is running but health check fails

**Check health endpoint:**
```bash
docker exec dualcaster-backend curl http://localhost:8000/api/health
```

**If it fails:**
- Database might not be accessible
- Health check endpoint might have issues
- Check database connection in logs

### Issue 4: Frontend Can't Reach Backend

**Symptom:** Frontend logs show connection errors

**Verify:**
1. Both containers are on the same network:
   ```bash
   docker network inspect mtg-market-intel_dualcaster-network
   ```

2. Backend service name is correct: `backend:8000`

3. Frontend can resolve backend:
   ```bash
   docker exec dualcaster-frontend nslookup backend
   ```

### Issue 5: Port Conflicts

**Symptom:** Backend can't bind to port 8000

**Check:**
```bash
# Check if port is already in use
netstat -tuln | grep 8000
# Or
lsof -i :8000
```

## Quick Fixes

### Restart All Services

```bash
docker compose -f docker-compose.production.yml down
docker compose -f docker-compose.production.yml up -d
```

### Rebuild Backend Only

```bash
docker compose -f docker-compose.production.yml build --no-cache backend
docker compose -f docker-compose.production.yml up -d backend
```

### Check Backend Health Manually

```bash
# Enter backend container
docker exec -it dualcaster-backend bash

# Test health endpoint
curl http://localhost:8000/api/health

# Check if uvicorn is running
ps aux | grep uvicorn
```

## Verification Steps

After fixing, verify:

1. **Backend is healthy:**
   ```bash
   docker compose -f docker-compose.production.yml ps backend
   # Should show "Up (healthy)"
   ```

2. **Health endpoint works:**
   ```bash
   curl http://localhost:8000/api/health
   # Should return JSON
   ```

3. **Frontend can reach backend:**
   ```bash
   docker exec dualcaster-frontend curl http://backend:8000/api/health
   # Should return JSON
   ```

4. **Frontend is running:**
   ```bash
   docker compose -f docker-compose.production.yml ps frontend
   # Should show "Up"
   ```

## Next Steps

If the issue persists after these checks:

1. Share the output of:
   ```bash
   docker compose -f docker-compose.production.yml ps
   docker logs dualcaster-backend --tail 50
   docker logs dualcaster-frontend --tail 50
   ```

2. Check if there are any firewall or network restrictions

3. Verify environment variables are set correctly:
   ```bash
   docker exec dualcaster-backend env | grep -E "POSTGRES|DATABASE|REDIS"
   ```

