import { Hono } from 'hono';
import { serve } from '@hono/node-server';
import { createServer, getServerPort } from '@devvit/web/server';
import { api, external } from './routes/api.js';
import { scheduler } from './routes/scheduler.js';

const app = new Hono();

app.get('/health', (c) => c.json({ ok: true, service: 'hellscube-bridge' }));
app.route('/api', api);
app.route('/external', external);
app.route('/internal/scheduler', scheduler);

serve({
  fetch: app.fetch,
  createServer,
  port: getServerPort(),
});
