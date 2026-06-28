# Shreya Patel — Portfolio

Interactive portfolio with 24 AI agent explorer and Claude-powered chatbot.

## Quick Start

```bash
# 1. Install dependencies
npm install

# 2. Run locally
npm run dev

# 3. Open http://localhost:5173
```

## Deploy to Vercel

```bash
# 1. Push to GitHub
git init
git add .
git commit -m "initial portfolio"
git remote add origin https://github.com/shreya-patel-PM/portfolio.git
git push -u origin main

# 2. Go to vercel.com → Add New Project → Import your repo
# 3. Vercel auto-detects Vite and deploys
```

## Enable the AI Chatbot (after deploying)

1. Get an API key at https://console.anthropic.com/settings/keys
2. In Vercel: Project Settings → Environment Variables
3. Add `ANTHROPIC_API_KEY` = your key
4. Redeploy

The `api/chat.js` file handles proxying requests so your key stays secret.

## Update Content

All data lives in `src/App.jsx`:
- `AGENTS` array — flip `shipped: true` when you ship an agent
- `EXPERIENCE` array — add/edit roles
- `SHREYA_CONTEXT` string — update so the chatbot knows your latest info
- `STACK` array — add new tools as you adopt them

## Tech Stack

React + Vite + Vercel Serverless Functions + Anthropic Claude API
