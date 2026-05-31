import type {
  GoldPriceResponse,
  IndicatorsResponse,
  SignalResponse,
  PredictionResponse,
  MacroResponse,
  NewsResponse,
  DebateResponse,
  StrategiesResponse,
  BacktestResult,
  HealthResponse,
  StatsResponse,
  QuickAnalysisResponse,
  ExtraDataResponse,
  CalendarResponse,
  FactorsResponse,
} from './types';

import { useEffect, useRef } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8001';

const WS_BASE = API_BASE.replace(/^http/, 'ws');

// ── Response cache (client-side, for instant remount) ──
const responseCache = new Map<string, { data: unknown; ts: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

export function getCached<T>(key: string): T | null {
  const entry = responseCache.get(key);
  if (entry && Date.now() - entry.ts < CACHE_TTL) return entry.data as T;
  responseCache.delete(key);
  return null;
}

// ── Request deduplication ──
const inflight = new Map<string, Promise<unknown>>();

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const key = `${options?.method || 'GET'}:${url}`;

  // Serve from cache for GET requests
  if (!options?.method || options.method === 'GET') {
    const cached = getCached<T>(key);
    if (cached) return cached;
  }

  const prev = inflight.get(key);
  if (prev) return prev as Promise<T>;

  const promise = (async () => {
    const res = await fetch(url, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options?.headers },
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(`HTTP ${res.status}${text ? ` — ${text.slice(0, 200)}` : ''}`);
    }
    const data = await res.json();
    // Cache GET responses
    if (!options?.method || options.method === 'GET') {
      responseCache.set(key, { data, ts: Date.now() });
    }
    return data;
  })();

  inflight.set(key, promise);
  promise.finally(() => { if (inflight.get(key) === promise) inflight.delete(key); });
  return promise as Promise<T>;
}

export const api = {
  health: () => fetchJson<HealthResponse>('/health'),

  stats: () => fetchJson<StatsResponse>('/stats'),

  gold: (source = 'intl', period = '1y') =>
    fetchJson<GoldPriceResponse>(`/api/analysis/gold?source=${source}&period=${period}`),

  indicators: (source = 'intl', period = '1y') =>
    fetchJson<IndicatorsResponse>(`/api/analysis/indicators?source=${source}&period=${period}`),

  signal: (source = 'intl', period = '1y') =>
    fetchJson<SignalResponse>(`/api/analysis/signal?source=${source}&period=${period}`),

  prediction: (source = 'intl', days = 7) =>
    fetchJson<PredictionResponse>(`/api/analysis/predict?source=${source}&days=${days}`),

  macro: (period = '1y') =>
    fetchJson<MacroResponse>(`/api/analysis/macro?period=${period}`),

  news: () => fetchJson<NewsResponse>('/api/analysis/news'),

  debate: () =>
    fetchJson<DebateResponse>('/api/debate/run', { method: 'POST' }),

  quick: () =>
    fetchJson<QuickAnalysisResponse>('/api/debate/quick'),

  strategies: () =>
    fetchJson<StrategiesResponse>('/api/backtest/strategies'),

  backtest: (strategy = 'golden_cross', period = '2y', initialCash = 100000) =>
    fetchJson<BacktestResult>(
      `/api/backtest/run?strategy=${strategy}&period=${period}&initial_cash=${initialCash}`,
    ),

  extraData: () => fetchJson<ExtraDataResponse>('/api/analysis/extra'),

  calendar: (days = 60) =>
    fetchJson<CalendarResponse>(`/api/analysis/calendar?days=${days}`),

  factors: () => fetchJson<FactorsResponse>('/api/analysis/factors'),
};

export function useWebSocket(
  clientId: string,
  channels: string[],
  onMessage: (channel: string, data: unknown) => void,
) {
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const url = `${WS_BASE}/ws/${clientId}`;
    const ws = new WebSocket(url);
    let reconnectTimer: ReturnType<typeof setTimeout>;

    ws.onopen = () => {
      for (const ch of channels) {
        ws.send(JSON.stringify({ type: 'subscribe', channel: ch }));
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.channel) {
          onMessage(msg.channel, msg.data);
        }
      } catch { /* ignore */ }
    };

    ws.onclose = () => {
      reconnectTimer = setTimeout(() => {
        wsRef.current = null;
      }, 5000);
    };

    wsRef.current = ws;

    return () => {
      clearTimeout(reconnectTimer);
      ws.close();
      wsRef.current = null;
    };
  }, [clientId, ...channels]);

  return wsRef;
}
