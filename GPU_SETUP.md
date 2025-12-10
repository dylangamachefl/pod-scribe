# GPU Setup Guide for Windows with WSL2

## Prerequisites

This guide assumes you want to run the transcription worker in Docker with GPU support on Windows.

---

## Step 1: Verify Your GPU

Check that you have an NVIDIA GPU:

```powershell
# In PowerShell
nvidia-smi
```

**Expected output:** GPU information (model, driver version, CUDA version)

**Required:** NVIDIA GPU with CUDA Compute Capability 3.5+ (most GPUs from 2014+)

---

## Step 2: Install/Update Windows NVIDIA Drivers

**IMPORTANT:** Install drivers on **Windows (host)**, NOT inside WSL2!

1. **Download latest drivers:**
   - Go to: https://www.nvidia.com/Download/index.aspx
   - Select your GPU model
   - Download the **Windows driver** (not Linux!)

2. **Install driver:**
   - Run the `.exe` installer on Windows
   - Restart if prompted

3. **Verify driver version:**
```powershell
nvidia-smi
```

**Required:** Driver version 510.x or newer for WSL2 GPU support

**What happens:** Windows drivers automatically "project" into WSL2 - no Linux driver installation needed!

---

## Step 3: Install WSL2 (if not already installed)

```powershell
# In PowerShell (Administrator)
wsl --install
```

**Restart** your computer after installation.

**Verify WSL2:**
```powershell
wsl --list --verbose
```

Should show VERSION 2 for your distro.

---

## Step 4: Verify GPU Access in WSL2

```bash
# In WSL2 terminal
nvidia-smi
```

**Expected:** Same GPU info as Windows PowerShell

**If this works:** GPU passthrough is working! 🎉

**If this fails:** 
- Check driver version (must be 510.x+)
- Ensure WSL2 is version 2 (not version 1)
- Update Windows (WSL2 GPU support requires Windows 11 or Windows 10 21H2+)

---

## Step 5: Install Docker Desktop

1. **Download:** https://www.docker.com/products/docker-desktop/
2. **Install** Docker Desktop for Windows
3. **Enable WSL2 backend:**
   - Settings → General → "Use the WSL 2 based engine" ✓
4. **Restart** Docker Desktop

---

## Step 6: Install NVIDIA Container Toolkit

This is the magic that lets Docker containers access your GPU!

**In WSL2 terminal:**

```bash
# Add NVIDIA package repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Update and install
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker to use NVIDIA runtime
sudo nvidia-ctk runtime configure --runtime=docker

# Restart Docker (from PowerShell)
```

**Then in PowerShell:**
```powershell
wsl --shutdown
# Wait 10 seconds, then restart Docker Desktop
```

---

## Step 7: Test GPU in Docker Container

```bash
# In WSL2 terminal
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

**Expected:** GPU information inside the container

**If this works:** Docker can access GPU! Ready to build transcription worker! 🚀

---

## Step 8: Build and Run Transcription Worker

```bash
# Navigate to project directory
cd /mnt/c/Users/Dylan/Projects/ai-portfolio/podcast-transcriber

# Build the transcription worker (first time: 10-20 min)
docker-compose build transcription-worker

# Run it
docker-compose up transcription-worker
```

**Expected:** Should see CUDA device information and transcription worker starting

---

## Troubleshooting

### "nvidia-smi not found in WSL2"
- **Cause:** Driver version too old or WSL2 not properly configured
- **Fix:** Update Windows NVIDIA drivers to 510.x or newer

### "docker: Error response from daemon: could not select device driver"
- **Cause:** nvidia-container-toolkit not installed or Docker not configured
- **Fix:** Re-run Step 6, ensure `sudo nvidia-ctk runtime configure` ran successfully

### "CUDA error: no kernel image is available"
- **Cause:** Docker image CUDA version incompatible with host driver
- **Fix:** Check `nvidia-smi` output for "CUDA Version", adjust Dockerfile to use compatible version

### Container builds but GPU not detected
- **Cause:** Runtime not specified or incorrect
- **Fix:** Ensure `runtime: nvidia` is in docker-compose.yml and nvidia-container-toolkit is installed

---

## Verification Checklist

Before building transcription worker, verify:

- [ ] `nvidia-smi` works in PowerShell
- [ ] `nvidia-smi` works in WSL2 terminal
- [ ] Driver version is 510.x or newer
- [ ] Docker Desktop is using WSL2 backend
- [ ] `docker run --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi` works
- [ ] nvidia-container-toolkit is installed in WSL2

**All checked?** You're ready to run GPU-accelerated transcription in Docker! 🎉

---

## Alternative: Keep Host-Based Transcription

If GPU setup is too complex, you can keep the current host-based transcription:

```bash
# Run transcription on host (as before)
conda activate podcast_bot
python transcription-service/src/cli.py

# Services still communicate via Redis events
# Just transcription runs outside Docker
```

This hybrid approach works fine for local development!
