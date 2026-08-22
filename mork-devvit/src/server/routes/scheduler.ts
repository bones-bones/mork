import { Hono } from 'hono';
import { runCardOfTheDay } from '../cardOfTheDay.js';
import { runDailyGallery } from '../dailyGallery.js';

type SchedulerTaskResponse = {
  status: 'ok' | 'error';
  message?: string;
  result?:
    | Awaited<ReturnType<typeof runCardOfTheDay>>
    | Awaited<ReturnType<typeof runDailyGallery>>;
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

scheduler.post('/daily-submissions-gallery', async (c) => {
  try {
    const result = await runDailyGallery();
    console.log('daily-submissions-gallery:', JSON.stringify(result));
    return c.json<SchedulerTaskResponse>({ status: 'ok', result }, 200);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error('daily-submissions-gallery failed:', message);
    return c.json<SchedulerTaskResponse>({ status: 'error', message }, 500);
  }
});
