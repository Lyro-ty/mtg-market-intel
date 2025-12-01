# Deployment Guide for dualcasterdeals.com

This guide covers deploying the Dualcaster Deals application to production.

## Prerequisites

- A server with Docker and Docker Compose installed
- Domain `dualcasterdeals.com` pointed to your server's IP
- SSH access to the server

## Initial Setup

### 1. Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose-plugin

# Add your user to docker group
sudo usermod -aG docker $USER
```

### 2. Clone Repository

```bash
git clone https://github.com/your-repo/mtg-market-intel.git
cd mtg-market-intel
```

### 3. Configure Environment

```bash
# Copy production environment template
cp env.production.example .env.production

# Generate a strong secret key
SECRET_KEY=$(openssl rand -hex 32)
echo "Generated SECRET_KEY: $SECRET_KEY"

# Edit the file with your values
nano .env.production
```

**Important**: Set a strong, unique value for:
- `SECRET_KEY` - Used for JWT token signing
- `POSTGRES_PASSWORD` - Database password
- API keys for OpenAI/Anthropic

### 4. SSL Certificate Setup

#### Option A: Let's Encrypt (Recommended)

```bash
# Create directories
mkdir -p certbot/conf certbot/www

# Get initial certificate (run nginx first for ACME challenge)
# Edit nginx.conf to temporarily serve on port 80 only

docker run -it --rm --name certbot \
  -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
  -v "$(pwd)/certbot/www:/var/www/certbot" \
  certbot/certbot certonly --webroot \
  -w /var/www/certbot \
  -d dualcasterdeals.com \
  -d www.dualcasterdeals.com \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email
```

#### Option B: Manual SSL (from GoDaddy)

If you purchased an SSL certificate from GoDaddy:

```bash
mkdir -p nginx/ssl

# Place your certificate files:
# - fullchain.pem (certificate + intermediate)
# - privkey.pem (private key)
```

Update `nginx/nginx.conf` to point to these files.

### 5. Deploy

```bash
# Build and start services
docker compose -f docker-compose.production.yml up -d --build

# Check status
docker compose -f docker-compose.production.yml ps

# View logs
docker compose -f docker-compose.production.yml logs -f
```

## Post-Deployment

### 1. Run Database Migrations

Migrations run automatically on backend startup, but you can run manually:

```bash
docker compose -f docker-compose.production.yml exec backend alembic upgrade head
```

### 2. Create Admin User

```bash
# Access backend shell
docker compose -f docker-compose.production.yml exec backend python

# Create admin user
>>> from app.db.session import async_session
>>> from app.services.auth import create_user
>>> from app.schemas.auth import UserRegister
>>> import asyncio

>>> async def create_admin():
...     async with async_session() as db:
...         user = await create_user(db, UserRegister(
...             email="admin@dualcasterdeals.com",
...             username="admin",
...             password="YourSecurePassword123",
...             display_name="Admin"
...         ))
...         user.is_admin = True
...         await db.commit()
...         print(f"Admin user created: {user.email}")

>>> asyncio.run(create_admin())
```

### 3. Verify Deployment

- Visit https://dualcasterdeals.com
- Check API health: https://dualcasterdeals.com/api/health
- Test login/registration

## Maintenance

### Updating the Application

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.production.yml up -d --build

# Check for issues
docker compose -f docker-compose.production.yml logs -f
```

### Database Backups

```bash
# Create backup
docker compose -f docker-compose.production.yml exec db \
  pg_dump -U dualcaster_user dualcaster_deals > backup_$(date +%Y%m%d).sql

# Restore from backup
docker compose -f docker-compose.production.yml exec -T db \
  psql -U dualcaster_user dualcaster_deals < backup_20240101.sql
```

### SSL Certificate Renewal

Certbot automatically renews certificates. To manually renew:

```bash
docker compose -f docker-compose.production.yml run --rm certbot renew
docker compose -f docker-compose.production.yml exec nginx nginx -s reload
```

### Viewing Logs

```bash
# All services
docker compose -f docker-compose.production.yml logs -f

# Specific service
docker compose -f docker-compose.production.yml logs -f backend

# Last 100 lines
docker compose -f docker-compose.production.yml logs --tail=100 backend
```

## Security Checklist

- [ ] Strong SECRET_KEY generated and set
- [ ] Strong database password set
- [ ] CORS_ORIGINS properly configured
- [ ] SSL certificate installed and working
- [ ] Firewall configured (only ports 80, 443 open)
- [ ] Regular backups scheduled
- [ ] Monitoring/alerting set up
- [ ] API rate limiting verified

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose -f docker-compose.production.yml logs backend

# Check container health
docker inspect dualcaster-backend | grep -A 10 Health
```

### Database connection issues

```bash
# Test database connection
docker compose -f docker-compose.production.yml exec db \
  psql -U dualcaster_user -d dualcaster_deals -c "SELECT 1"
```

### SSL issues

```bash
# Test SSL configuration
curl -v https://dualcasterdeals.com/health

# Check certificate
openssl s_client -connect dualcasterdeals.com:443 -servername dualcasterdeals.com
```

## GoDaddy DNS Configuration

Point your domain to your server:

1. Log in to GoDaddy Domain Manager
2. Go to DNS Management for dualcasterdeals.com
3. Set records:
   - A record: `@` → Your server IP
   - A record: `www` → Your server IP
   - (Optional) AAAA records for IPv6

Wait for DNS propagation (usually 15 minutes to 48 hours).


