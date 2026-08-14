import { Hono } from 'hono';
import { serve } from '@hono/node-server';
import { createServer, getServerPort } from '@devvit/web/server';
import { api } from './routes/api.js';

const app = new Hono();

app.get('/health', (c) => c.json({ ok: true, service: 'mork-hellscube-bridge' }));
app.route('/api', api);

serve({
  fetch: app.fetch,
  createServer,
  port: getServerPort(),
});
