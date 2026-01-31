# Dexter Speaks - AAC Application

An Augmentative and Alternative Communication (AAC) application built with NiceGUI and Python.

## Features

- 📱 Touch-friendly interface for communication
- 🔊 Text-to-speech for item labels
- 🖼️ Image support for visual communication
- 👨‍💼 Admin mode with PIN protection
- 📂 Category organization with custom ordering
- 🗑️ Recycle bin for deleted items
- 👁️ Visibility controls for items and categories

## Docker Deployment (Unraid)

### Quick Start

1. **Build and run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

2. **Access the application:**
   - Open your browser to `http://your-server-ip:8080`

### Manual Docker Commands

**Build the image:**
```bash
docker build -t dexter-speaks .
```

**Run the container:**
```bash
docker run -d \
  --name dexter-speaks \
  -p 8080:8080 \
  -v /mnt/user/appdata/aac_app_dex:/app/data \
  --restart unless-stopped \
  dexter-speaks
```

### Unraid Template

For Unraid, you can create a custom template with these settings:

- **Repository:** `dexter-speaks` (after building locally or pushing to Docker Hub)
- **Port:** `8080` → `8080`
- **Volume:** `/mnt/user/appdata/aac_app_dex` → `/app/data`
- **Restart Policy:** `unless-stopped`

## Data Folder Structure

The `/app/data` volume contains:

```
data/
├── config.yaml          # PIN and category settings
├── usage.log           # Usage statistics
├── Food/               # Category folders
│   ├── item1.yaml
│   ├── item1.jpg
│   └── ...
├── Feelings/
└── ...
```

## Configuration

### PIN Management

- Default PIN: `1234`
- Change PIN in admin mode via "Change Pin" button
- PIN is stored in `data/config.yaml`

### Category Ordering

- Use up/down arrows in admin mode to reorder categories
- Order is saved in `data/config.yaml`

### Environment Variables

- `AAC_DATA_DIR`: Path to data directory (default: `data`)

## Development

### Local Setup

1. **Create virtual environment:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python app.py
   ```

4. **Access locally:**
   - Open `http://localhost:8080`

## Tech Stack

- **Backend:** Python 3.11+
- **Web Framework:** NiceGUI (FastAPI + Vue)
- **Data Storage:** YAML files
- **Image Processing:** Pillow
- **Deployment:** Docker

## License

Private use only.
