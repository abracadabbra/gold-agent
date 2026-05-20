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
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}${text ? ` — ${text.slice(0, 200)}` : ''}`);
  }
  return res.json();
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
};
