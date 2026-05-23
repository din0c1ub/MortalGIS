---
title: MortalGIS - Ethical Spatial Anonymization & Mortality Data Sandbox
emoji: 🛡️
colorFrom: red
colorTo: zinc
sdk: static
pinned: false
---

# MortalGIS 🛡️

A highly polished, interactive, mobile-responsive web application designed to demonstrate **Ethical & Legal GIS sanitation workflows for post-mortem privacy**. Bypassing direct address pointing, MortalGIS simulates in-memory data minimization, PostGIS spatial queries, and compliance scoring.

## 🚀 Hugging Face Spaces Deployment Guide

Since this is a client-side single page app (SPA) powered by Vite, React, and Leaflet, it can be hosted **100% free** on Hugging Face Spaces using the **Static SDK**.

### Option A: Automatic Push via Git (Recommended)

1. **Create a Space on Hugging Face**:
   - Go to [huggingface.co/new-space](https://huggingface.co/new-space)
   - Choose a name (e.g., `mortalgis`)
   - Select **Static** as the SDK.
   - Choose the **Public** or **Private** visibility.

2. **Clone the Space Repository locally**:
   ```bash
   git clone https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
   ```

3. **Build the Portal App**:
   Run the build script in this workspace folder to compile the static site:
   ```bash
   npm run build
   ```
   This will generate a highly optimized bundle inside the `dist/` folder.

4. **Copy built files to your Space repo**:
   Copy the entire *contents* of the `dist/` directory into your cloned Hugging Face Space directory:
   ```bash
   cp -r dist/* /path/to/cloned/hf/space/
   # Also copy this README.md so Hugging Face registers the Static configuration metadata
   cp README.md /path/to/cloned/hf/space/
   ```

5. **Commit and Push**:
   ```bash
   cd /path/to/cloned/hf/space/
   git add .
   git commit -m "Deploy MortalGIS app to Hugging Face Spaces"
   git push origin main
   ```
   *Within seconds, Hugging Face will build and publish your app online!*

---

### Option B: Built-in Direct Upload via the Web UI

If you don't want to use the Git terminal, you can upload compiled assets directly:

1. Create your Static Space on [huggingface.co/new-space](https://huggingface.co/new-space).
2. Build the app locally using `npm run build`.
3. In your Space's browser window, click **Files and versions** -> **Add file** -> **Upload files**.
4. Drag and drop all the files inside the `dist/` directory (including the `assets/` subfolder, `index.html`, any logos) and this `README.md` file to the root of the upload box.
5. Commit changes directly on the web interface.

---

## 🔄 Path 1: Zero-Cost Automated "Static CI/CD Rebuild" Pipeline

This repository is pre-configured with a dual-stage, serverless pipeline:
1. **Scraping & PII Minimization**: Standardizes unstructured sources, strips names, rounds dates, map exact ages to 10-year groups, and snaps locations into a safe **80m Physical Grid**.
2. **Commit & Bake**: Writes the update directly into `/src/anonymized_database.json`, rebuilding the client portal with fresh records daily.

### 💻 Running Locally

You can manually trigger and review local scrapes at any time:
```bash
# 1. Runs the Node scraper + 80m Grid Snapping Pipeline
npm run scrape

# 2. Compiles your React App with the fresh baked records
npm run build
```

### 🤖 Nightly Automated Rebuild (GitHub Actions Setup)

To have GitHub automatically harvest public logs, de-identify them, and redeploy them to your static Hugging Face space every night completely free:

1. Create a repository on GitHub and push this project codebase.
2. In your GitHub repo settings, go to **Settings** -> **Secrets and variables** -> **Actions** -> **Repository Secrets**.
3. Create three secrets:
   - `HF_USERNAME`: Your Hugging Face user profile handle (e.g. `joelrakowski`).
   - `HF_SPACE_NAME`: The Exact name of the Static Space you set up (e.g. `mortalgis`).
   - `HF_TOKEN`: A Hugging Face **User Access Token** with `write` permissions (Generate one at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)).
4. Commit the pipeline definition `.github/workflows/deploy.yml`. 

*Your workflow is now active! GitHub will trigger a run every night, pull incoming RSS/Examiner entries, sanitize and anonymize them, and push the newly built static applet to Hugging Face with no server overhead.*

---

## 🛠️ Tech Stack & Key Modules

- **Core UI**: React 19, TypeScript, Tailwind CSS v4, Motion Transitions.
- **Geodata Visualizer**: Leaflet with dark high-contrast map themes.
- **PII Scrubbing Pipeline**: Algorithmic / Regex patterns running entirely in-memory prior to coordinate aggregation.
- **Compliance Scorecard**: Dynamic checklist verifying geodemographic safety markers in real-time.
- **Historical Analysis**: Decadal filters supporting archive mapping back to regional legacy records from the 1980s.
