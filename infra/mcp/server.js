const express = require('express');
const bodyParser = require('body-parser');
const axios = require('axios');

const app = express();
app.use(bodyParser.json());

app.use((req, _res, next) => {
  console.log(`[mcp-proxy] ${req.method} ${req.path}`);
  next();
});

const PORT = process.env.PORT || 3001;
const DEFAULT_TOKEN = process.env.GITHUB_PAT || process.env.GITHUB_TOKEN || '';

/**
 * Create a GitHub API client. Accepts an optional token override from the request.
 * If token is provided in the request, use it; otherwise fall back to env token.
 */
function ghClient(tokenOverride) {
  const token = tokenOverride || DEFAULT_TOKEN;
  const headers = {
    'User-Agent': 'mcp-metrics-proxy',
    'Accept': 'application/vnd.github+json',
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return axios.create({ baseURL: 'https://api.github.com', headers, timeout: 30000 });
}

app.post('/list_commits', async (req, res) => {
  const { repo, since, until, token } = req.body || {};
  if (!repo) return res.status(400).json({ error: 'repo is required' });
  try {
    const client = ghClient(token);
    const resp = await client.get(`/repos/${repo}/commits`, { params: { since, until, per_page: 100 } });
    res.json(resp.data);
  } catch (err) {
    const status = err.response?.status || 500;
    res.status(status).json({ error: err.message, data: err.response?.data });
  }
});

app.post('/list_pull_requests', async (req, res) => {
  const { repo, state = 'closed', since, token } = req.body || {};
  if (!repo) return res.status(400).json({ error: 'repo is required' });
  try {
    const client = ghClient(token);
    const params = { state, per_page: 100, sort: 'updated', direction: 'desc' };
    if (since) params['since'] = since;
    const resp = await client.get(`/repos/${repo}/pulls`, { params });
    let items = resp.data;
    if (since) {
      items = items.filter((p) => p.updated_at >= since);
    }
    res.json(items);
  } catch (err) {
    const status = err.response?.status || 500;
    res.status(status).json({ error: err.message, data: err.response?.data });
  }
});

app.post('/list_issues', async (req, res) => {
  const { repo, state = 'open', since, token } = req.body || {};
  if (!repo) return res.status(400).json({ error: 'repo is required' });
  try {
    const client = ghClient(token);
    const resp = await client.get(`/repos/${repo}/issues`, { params: { state, since, per_page: 100 } });
    res.json(resp.data);
  } catch (err) {
    const status = err.response?.status || 500;
    res.status(status).json({ error: err.message, data: err.response?.data });
  }
});

app.get('/health', (req, res) => {
  res.json({ status: 'ok', transport: 'http', auth: !!DEFAULT_TOKEN });
});

app.listen(PORT, () => {
  console.log(`GitHub proxy listening on ${PORT}`);
});
