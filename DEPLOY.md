# Ms t-SNE Explorer — Deployment Guide
# Server: Intel i7-12700, 62GB RAM, RTX 3080 (10GB VRAM)
# Access via: ssh ams.lab  (Tailscale: 100.100.31.114)

## 1. Clone / copy repo to server

```bash
# From your local machine
scp -r ms-tsne-explorer/ ams.lab:~/Desktop/vannuth/UNamur/ms-tsne-explorer/
# OR use VS Code Remote SSH + drag/drop
```

## 2. Install Docker + nvidia-container-toolkit (if not already)

```bash
# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

# NVIDIA Container Toolkit (for GPU passthrough)
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

## 3. Build and start

```bash
cd ~/Desktop/vannuth/UNamur/ms-tsne-explorer/

# First time (builds images)
docker compose up --build -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

## 4. Access the app

- Web UI:  http://100.100.31.114:3000   (via Tailscale from your laptop)
- API:     http://100.100.31.114:3000/api/gpu-status

## 5. Check GPU is passed through

```bash
docker exec mstsne_backend python3 -c "import cupy as cp; print(cp.cuda.runtime.getDeviceProperties(0)['name'])"
```

## 6. CPU-only mode (no GPU)

Edit docker-compose.yml and remove the `deploy.resources.reservations` section for the backend service.

## 7. Temp file management

Experiment files (embeddings, figures) are stored in the `tmp_data` Docker volume.
Auto-cleaned after 2 hours (configurable via TMP_TTL in backend/api/main.py).
To manually clear: `docker volume rm ms-tsne-explorer_tmp_data`

## 8. Update after code changes

```bash
# Rebuild only changed service
docker compose up --build -d backend    # backend changes
docker compose up --build -d frontend   # frontend changes
docker compose up --build -d            # both
```

## 9. Run in tmux (keep alive on SSH disconnect)

```bash
tmux new -s mstsne
cd ~/Desktop/vannuth/UNamur/ms-tsne-explorer/
docker compose up --build
# Ctrl+B, D to detach
# tmux attach -t mstsne to reattach
```
