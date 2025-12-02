# Docker Build Fixes

## Issues Fixed

### 1. **Backend: Pip Timeout for Large Packages** ✅
- **Problem:** Large packages like `torch` and `sentence-transformers` can cause pip install to timeout
- **Fix:** Added `--default-timeout=1000` to pip install command in `backend/Dockerfile`
- **Location:** `backend/Dockerfile` line 25

### 2. **Frontend: package-lock.json Out of Sync** ✅
- **Problem:** `npm ci` fails when package-lock.json is out of sync with package.json (common with sharp package)
- **Fix:** Changed to use `npm install` instead of `npm ci` to handle lock file mismatches gracefully
- **Location:** `frontend/Dockerfile.production` line 12
- **Note:** `npm install` will update the lock file if needed, which is acceptable for Docker builds

### 3. **Frontend: Standalone Build Verification** ✅
- **Problem:** No verification that Next.js standalone build completed successfully
- **Fix:** Added check to verify server.js exists after copying standalone output
- **Location:** `frontend/Dockerfile.production` line 42

## Build Instructions

After these fixes, rebuild with:

```bash
docker compose -f docker-compose.production.yml build --no-cache
```

## Common Build Issues and Solutions

### Backend Build Fails on pip install

**Symptoms:** Build hangs or fails when installing torch/sentence-transformers

**Solutions:**
1. ✅ Already fixed: Increased pip timeout to 1000 seconds
2. If still failing, try building with more memory:
   ```bash
   docker build --memory=4g -f backend/Dockerfile backend/
   ```
3. Consider using a multi-stage build to cache large dependencies separately

### Frontend Build Fails - Missing standalone directory

**Symptoms:** Error about `.next/standalone` not found

**Solutions:**
1. ✅ Already fixed: Added verification step
2. Ensure `next.config.js` has `output: 'standalone'` (already configured)
3. Check build logs for Next.js errors:
   ```bash
   docker compose -f docker-compose.production.yml build frontend 2>&1 | grep -A 20 "error"
   ```

### Build Timeouts

**Symptoms:** Build process times out

**Solutions:**
1. Increase Docker build timeout:
   ```bash
   export DOCKER_CLIENT_TIMEOUT=600
   export COMPOSE_HTTP_TIMEOUT=600
   ```
2. Build services individually:
   ```bash
   docker compose -f docker-compose.production.yml build backend
   docker compose -f docker-compose.production.yml build frontend
   ```

## Verification

After successful build, verify images:

```bash
docker images | grep dualcaster
```

You should see:
- `mtg-market-intel-backend`
- `mtg-market-intel-frontend`
- `mtg-market-intel-worker`
- `mtg-market-intel-scheduler`

## Next Steps

If builds still fail, check:

1. **Backend logs:**
   ```bash
   docker compose -f docker-compose.production.yml build backend 2>&1 | tee backend-build.log
   ```

2. **Frontend logs:**
   ```bash
   docker compose -f docker-compose.production.yml build frontend 2>&1 | tee frontend-build.log
   ```

3. **Check for specific errors:**
   - Python dependency conflicts
   - Node.js version mismatches
   - Missing system dependencies
   - Network issues downloading packages

