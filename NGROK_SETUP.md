# Ngrok Setup Guide for Unraid

## Overview
Ngrok creates a secure tunnel to expose your Dexter Speaks app to the internet without opening ports on your router or dealing with dynamic DNS.

## Prerequisites
- Ngrok account (free tier works fine)
- Your app running on Unraid (port 8085)

## Step 1: Get Ngrok Auth Token

1. **Sign up for ngrok:** https://ngrok.com/
2. **Login to dashboard:** https://dashboard.ngrok.com/
3. **Copy your authtoken** from the "Your Authtoken" section

## Step 2: Deploy Ngrok Container on Unraid

### Option A: Using Unraid Docker UI (Recommended)

1. **Go to Unraid Docker tab**
2. **Click "Add Container"**
3. **Fill in the following:**

   - **Name:** `ngrok`
   - **Repository:** `ngrok/ngrok:latest`
   - **Network Type:** `bridge`
   - **Console shell command:** `bash`
   
   **Port Mappings:**
   - Container Port: `4040` → Host Port: `4040` (ngrok web interface)
   
   **Environment Variables:**
   - **Name:** `NGROK_AUTHTOKEN`
   - **Value:** `your-authtoken-from-step-1`
   
   - **Name:** `NGROK_CONFIG`
   - **Value:** `/etc/ngrok.yml`

   **Extra Parameters:**
   ```
   --command='http 172.17.0.1:8085'
   ```
   
   > **Note:** `172.17.0.1` is the Docker bridge IP that allows ngrok to access your host's port 8085

4. **Click "Apply"**

### Option B: Using Docker Command Line

Open Unraid terminal and run:

```bash
docker run -d \
  --name ngrok \
  -e NGROK_AUTHTOKEN=your-authtoken-here \
  -p 4040:4040 \
  --restart unless-stopped \
  ngrok/ngrok:latest \
  http host.docker.internal:8085
```

**For Unraid specifically, use:**
```bash
docker run -d \
  --name ngrok \
  -e NGROK_AUTHTOKEN=your-authtoken-here \
  -p 4040:4040 \
  --add-host=host.docker.internal:host-gateway \
  --restart unless-stopped \
  ngrok/ngrok:latest \
  http host.docker.internal:8085
```

## Step 3: Get Your Public URL

### Method 1: Ngrok Web Interface
1. Open browser: `http://your-unraid-ip:4040`
2. You'll see the ngrok dashboard
3. Copy the **Forwarding URL** (looks like `https://xxxx-xx-xx-xx-xx.ngrok-free.app`)

### Method 2: Check Logs
```bash
docker logs ngrok
```

Look for a line like:
```
Forwarding  https://xxxx-xx-xx-xx-xx.ngrok-free.app -> http://host.docker.internal:8085
```

## Step 4: Access Your App

Share this URL with anyone:
```
https://xxxx-xx-xx-xx-xx.ngrok-free.app
```

They can access your app from anywhere in the world! 🌍

## Ngrok Free Tier Limitations

⚠️ **Important Notes:**
- URL changes every time ngrok restarts (unless you upgrade to paid)
- Session timeout after 2 hours of inactivity (free tier)
- Limited to 1 online ngrok process
- Shows ngrok warning page before accessing your app

## Upgrade to Paid (Optional)

**Benefits:**
- **Custom subdomain:** `https://dexter-speaks.ngrok.app` (stays the same)
- **No session timeout**
- **No warning page**
- **Multiple tunnels**

**Pricing:** ~$8/month for Personal plan

### To use custom domain (paid):
```bash
docker run -d \
  --name ngrok \
  -e NGROK_AUTHTOKEN=your-authtoken-here \
  -p 4040:4040 \
  --add-host=host.docker.internal:host-gateway \
  --restart unless-stopped \
  ngrok/ngrok:latest \
  http host.docker.internal:8085 --domain=dexter-speaks.ngrok.app
```

## Advanced: Persistent Configuration

Create a config file for more control:

### 1. Create ngrok config directory
```bash
mkdir -p /mnt/user/appdata/ngrok
```

### 2. Create config file
```bash
nano /mnt/user/appdata/ngrok/ngrok.yml
```

Add this content:
```yaml
version: 2
authtoken: your-authtoken-here
tunnels:
  dexter-speaks:
    proto: http
    addr: host.docker.internal:8085
    # Optional: Add basic auth for extra security
    # auth: "username:password"
    # Optional: Custom domain (paid plan only)
    # domain: dexter-speaks.ngrok.app
```

### 3. Run with config file
```bash
docker run -d \
  --name ngrok \
  -v /mnt/user/appdata/ngrok/ngrok.yml:/etc/ngrok.yml \
  -p 4040:4040 \
  --add-host=host.docker.internal:host-gateway \
  --restart unless-stopped \
  ngrok/ngrok:latest \
  start --all --config /etc/ngrok.yml
```

## Security Recommendations

### 1. Enable HTTPS Only
Ngrok provides HTTPS by default - always share the `https://` URL, not `http://`

### 2. Add Basic Authentication (Optional)
In your ngrok config:
```yaml
tunnels:
  dexter-speaks:
    proto: http
    addr: host.docker.internal:8085
    auth: "admin:your-secure-password"
```

### 3. Use IP Restrictions (Paid Plan)
Limit access to specific IP addresses:
```yaml
tunnels:
  dexter-speaks:
    proto: http
    addr: host.docker.internal:8085
    ip_restriction:
      allow_cidrs:
        - 1.2.3.4/32  # Specific IP
```

### 4. Monitor Access
Check ngrok dashboard at `http://your-unraid-ip:4040` to see:
- All requests
- Response times
- IP addresses accessing your app

## Troubleshooting

### Ngrok can't connect to app
```bash
# Check if dexter-speaks is running
docker ps | grep dexter-speaks

# Check ngrok logs
docker logs ngrok

# Verify port 8085 is accessible
curl http://localhost:8085
```

### Get new URL after restart
```bash
# View logs to see new URL
docker logs ngrok | grep Forwarding

# Or check web interface
# http://your-unraid-ip:4040
```

### Restart ngrok
```bash
docker restart ngrok
```

### Remove and recreate
```bash
docker stop ngrok
docker rm ngrok
# Then run the docker run command again
```

## Alternative: Cloudflare Tunnel (Free Alternative)

If you want a free permanent URL without ngrok limitations:

1. **Sign up for Cloudflare** (free)
2. **Use cloudflared tunnel**
3. **Get permanent subdomain** like `dexter-speaks.your-domain.com`

Let me know if you want a guide for Cloudflare Tunnel instead!

## Quick Reference

**Start ngrok:**
```bash
docker start ngrok
```

**Stop ngrok:**
```bash
docker stop ngrok
```

**View URL:**
```bash
docker logs ngrok | grep Forwarding
```

**Web Interface:**
```
http://your-unraid-ip:4040
```

**Your App (local):**
```
http://your-unraid-ip:8085
```

**Your App (public via ngrok):**
```
https://xxxx-xx-xx-xx-xx.ngrok-free.app
```
