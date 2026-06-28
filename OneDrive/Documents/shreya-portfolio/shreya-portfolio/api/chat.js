// This serverless function proxies chat requests to Anthropic's API
// so your API key stays secret (never exposed in the browser).
//
// SETUP:
// 1. Go to https://console.anthropic.com/settings/keys
// 2. Create a new API key
// 3. In your Vercel project dashboard: Settings → Environment Variables
//    Add: ANTHROPIC_API_KEY = sk-ant-... (your key)
// 4. Redeploy

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return res.status(500).json({ error: 'ANTHROPIC_API_KEY not configured' });
  }

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify(req.body),
    });

    const data = await response.json();
    return res.status(response.status).json(data);
  } catch (error) {
    return res.status(500).json({ error: 'Failed to reach Anthropic API' });
  }
}
