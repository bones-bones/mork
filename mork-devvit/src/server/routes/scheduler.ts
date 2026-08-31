import { Hono } from 'hono';
import { runCardOfTheDay } from '../cardOfTheDay.js';

type SchedulerTaskResponse = {
  status: 'ok' | 'error';
  message?: string;
  result?: Awaited<ReturnType<typeof runCardOfTheDay>>;
};

export const scheduler = new Hono();

scheduler.post('/card-of-the-day', async (c) => {
  try {
    const result = await runCardOfTheDay();
    console.log('card-of-the-day:', JSON.stringify(result));
    return c.json<SchedulerTaskResponse>({ status: 'ok', result }, 200);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error('card-of-the-day failed:', message);
    return c.json<SchedulerTaskResponse>({ status: 'error', message }, 500);
  }
});
