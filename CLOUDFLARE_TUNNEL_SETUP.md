# Cloudflare Tunnel Setup for dualcasterdeals.com

## Prerequisites
- Cloudflare account with `dualcasterdeals.com` domain
- `cloudflared` installed on your server
- Docker containers running on localhost:3000

## Step 1: Check Existing Tunnel

```bash
# List all tunnels
cloudflared tunnel list

# If "dualcaster" tunnel exists, get its ID
cloudflared tunnel info dualcaster
```

## Step 2: Create or Update Tunnel

### Option A: Use Existing Tunnel
If you have an existing tunnel named "dualcaster":

```bash
# Get tunnel ID
TUNNEL_ID=$(cloudflared tunnel list | grep dualcaster | awk '{print $1}')
echo "Tunnel ID: $TUNNEL_ID"
```

### Option B: Create New Tunnel
If you need to create a new tunnel:

```bash
# Create new tunnel
cloudflared tunnel create dualcaster

# This will output a tunnel ID and create credentials file
# Note the tunnel ID and credentials file path
```

## Step 3: Configure Tunnel

Create or update `~/.cloudflared/config.yml` (or `./cloudflared-config.yml`):

```yaml
tunnel: <your-tunnel-id>
credentials-file: /path/to/credentials.json

ingress:
  # Main domain
  - hostname: dualcasterdeals.com
    service: http://localhost:3000
  
  # WWW subdomain
  - hostname: www.dualcasterdeals.com
    service: http://localhost:3000
  
  # Catch-all
  - service: http_status:404
```

**Important**: Replace:
- `<your-tunnel-id>` with your actual tunnel ID
- `/path/to/credentials.json` with the actual path to your credentials file

## Step 4: Configure DNS in Cloudflare

### Via Cloudflare Dashboard:
1. Go to Cloudflare Dashboard → Your Domain → DNS
2. Delete any existing A records for `dualcasterdeals.com` and `www.dualcasterdeals.com`
3. Add CNAME records:
   - **Name**: `@` (or `dualcasterdeals.com`)
     **Target**: `<tunnel-id>.cfargotunnel.com`
     **Proxy**: Proxied (orange cloud)
   - **Name**: `www`
     **Target**: `<tunnel-id>.cfargotunnel.com`
     **Proxy**: Proxied (orange cloud)

### Via Command Line:
```bash
# Route DNS for main domain
cloudflared tunnel route dns dualcaster dualcasterdeals.com

# Route DNS for www subdomain
cloudflared tunnel route dns dualcaster www.dualcasterdeals.com
```

## Step 5: Update Environment Variables

Make sure your `.env` file has:

```env
DOMAIN=dualcasterdeals.com
FRONTEND_URL=https://dualcasterdeals.com
NEXT_PUBLIC_API_URL=/api
CORS_ORIGINS=["https://dualcasterdeals.com", "https://www.dualcasterdeals.com"]
```

Then restart your containers:
```bash
docker compose -f docker-compose.production.yml down
docker compose -f docker-compose.production.yml up -d
```

## Step 6: Run the Tunnel

### Option A: Run Directly (for testing)
```bash
# Run tunnel with config file
cloudflared tunnel --config ~/.cloudflared/config.yml run dualcaster

# Or if config is in current directory
cloudflared tunnel --config ./cloudflared-config.yml run dualcaster
```

### Option B: Run as System Service (recommended for production)

#### Linux (systemd):
```bash
# Install cloudflared as a service
sudo cloudflared service install

# Edit the service file to use your config
sudo nano /etc/systemd/system/cloudflared.service

# Update ExecStart to:
# ExecStart=/usr/local/bin/cloudflared tunnel --config /path/to/config.yml run dualcaster

# Enable and start
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
sudo systemctl status cloudflared
```

#### Windows (as a service):
```powershell
# Install as Windows service
cloudflared service install

# Configure in Windows Services
# Set startup to use: cloudflared tunnel --config C:\path\to\config.yml run dualcaster
```

## Step 7: Verify Setup

1. **Check tunnel status:**
   ```bash
   cloudflared tunnel info dualcaster
   ```

2. **Test locally:**
   ```bash
   # Make sure your frontend is running
   curl http://localhost:3000
   ```

3. **Test via domain:**
   ```bash
   curl https://dualcasterdeals.com
   ```

4. **Check Cloudflare Dashboard:**
   - Go to Zero Trust → Networks → Tunnels
   - Verify your tunnel shows as "Healthy"

## Troubleshooting

### Tunnel not connecting:
- Verify Docker containers are running: `docker ps`
- Check frontend is accessible: `curl http://localhost:3000`
- Verify tunnel credentials file exists and is readable
- Check tunnel logs: `cloudflared tunnel run dualcaster --loglevel debug`

### DNS not resolving:
- Wait 5-10 minutes for DNS propagation
- Verify CNAME records in Cloudflare dashboard
- Check DNS with: `dig dualcasterdeals.com` or `nslookup dualcasterdeals.com`

### 502 Bad Gateway:
- Frontend container might not be running
- Check: `docker logs dualcaster-frontend`
- Verify port 3000 is accessible: `netstat -tuln | grep 3000`

### CORS errors:
- Verify `CORS_ORIGINS` in `.env` includes your domain
- Restart backend after updating `.env`

## Security Notes

- Cloudflare Tunnel provides automatic HTTPS (no need for SSL certificates)
- All traffic is encrypted between Cloudflare and your server
- Your server doesn't need to expose ports to the internet
- Rate limiting is handled by Cloudflare

## Monitoring

View tunnel metrics in Cloudflare Dashboard:
- Zero Trust → Networks → Tunnels → [Your Tunnel] → Metrics

Check logs:
```bash
# If running as service
sudo journalctl -u cloudflared -f

# If running directly
cloudflared tunnel run dualcaster --loglevel info
```

