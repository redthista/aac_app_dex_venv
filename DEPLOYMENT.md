# Deployment Guide: Windows PC → Unraid Server

## Prerequisites
- Unraid server accessible on your network
- SSH access to Unraid (enabled in Unraid settings)
- Your Windows PC on the same network

## Step-by-Step Deployment

### Step 1: Enable SSH on Unraid (if not already enabled)

1. Open Unraid web interface: `http://your-unraid-ip`
2. Go to **Settings** → **Management Access**
3. Enable **SSH** and set to **Enabled**
4. Click **Apply**

### Step 2: Copy Files from Windows to Unraid

You have two options:

#### Option A: Using WinSCP (Recommended - GUI)

1. **Download WinSCP:** https://winscp.net/eng/download.php

2. **Connect to Unraid:**
   - Host name: `your-unraid-ip`
   - Port: `22`
   - User name: `root`
   - Password: Your Unraid root password
   - Click **Login**

3. **Create app directory:**
   - Navigate to `/mnt/user/appdata/`
   - Create new folder: `aac_app_dex`

4. **Upload files:**
   - Upload these files from `d:\aac_app_dex_venv\` to `/mnt/user/appdata/aac_app_dex/`:
     - `app.py`
     - `data_manager.py`
     - `requirements.txt`
     - `Dockerfile`
     - `docker-compose.yml`
     - `.dockerignore`
   
5. **Upload data folder:**
   - Upload entire `data` folder to `/mnt/user/appdata/aac_app_dex/data`
   - This includes all your categories, images, and config.yaml

#### Option B: Using PowerShell/SCP (Command Line)

```powershell
# From PowerShell on Windows (in d:\aac_app_dex_venv\)

# Install OpenSSH client if needed (Windows 10/11 usually has it)

# Copy application files
scp app.py data_manager.py requirements.txt Dockerfile docker-compose.yml .dockerignore root@your-unraid-ip:/mnt/user/appdata/aac_app_dex/

# Copy data folder
scp -r data root@your-unraid-ip:/mnt/user/appdata/aac_app_dex/
```

### Step 3: Connect to Unraid via SSH

**Using PowerShell:**
```powershell
ssh root@your-unraid-ip
# Enter your Unraid root password when prompted
```

**Or use PuTTY:**
- Download: https://www.putty.org/
- Host: `your-unraid-ip`
- Port: `22`
- Click **Open**
- Login as `root`

### Step 4: Build and Run on Unraid

Once connected via SSH:

```bash
# Navigate to app directory
cd /mnt/user/appdata/aac_app_dex

# Verify files are there
ls -la

# Build the Docker image
docker build -t dexter-speaks .

# Run the container
docker run -d \
  --name dexter-speaks \
  -p 8080:8080 \
  -v /mnt/user/appdata/aac_app_dex/data:/app/data \
  --restart unless-stopped \
  dexter-speaks

# Check if it's running
docker ps | grep dexter-speaks
```

### Step 5: Access Your App

Open your browser and go to:
- `http://your-unraid-ip:8080`

## Troubleshooting

### Check Container Logs
```bash
docker logs dexter-speaks
```

### Restart Container
```bash
docker restart dexter-speaks
```

### Stop Container
```bash
docker stop dexter-speaks
docker rm dexter-speaks
```

### Rebuild After Changes
```bash
cd /mnt/user/appdata/aac_app_dex
docker stop dexter-speaks
docker rm dexter-speaks
docker build -t dexter-speaks .
docker run -d --name dexter-speaks -p 8080:8080 -v /mnt/user/appdata/aac_app_dex/data:/app/data --restart unless-stopped dexter-speaks
```

## File Structure on Unraid

After deployment, your Unraid structure will be:

```
/mnt/user/appdata/aac_app_dex/
├── app.py
├── data_manager.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
└── data/
    ├── config.yaml
    ├── usage.log
    ├── Food/
    ├── Feelings/
    └── ...
```

## Quick Reference

**Your Unraid IP:** Find it in Unraid web interface or run `ifconfig` in Unraid terminal

**Default Ports:**
- App: `8080`
- SSH: `22`

**Important Paths:**
- App files: `/mnt/user/appdata/aac_app_dex/`
- Data folder: `/mnt/user/appdata/aac_app_dex/data/`

## Next Steps

1. Test the app works at `http://your-unraid-ip:8080`
2. Set up Unraid to auto-start the container (it will with `--restart unless-stopped`)
3. Optional: Set up reverse proxy with nginx if you want HTTPS
4. Optional: Add to Unraid's Docker tab for easier management

## Making Updates

When you make changes on your Windows PC:

1. Copy updated files to Unraid (using WinSCP or SCP)
2. Rebuild and restart the container:
   ```bash
   cd /mnt/user/appdata/aac_app_dex
   docker stop dexter-speaks
   docker rm dexter-speaks
   docker build -t dexter-speaks .
   docker run -d --name dexter-speaks -p 8080:8080 -v /mnt/user/appdata/aac_app_dex/data:/app/data --restart unless-stopped dexter-speaks
   ```
