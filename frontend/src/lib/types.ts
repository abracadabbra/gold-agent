export interface OhlcvPoint {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
}

export interface GoldPriceResponse {
  source: string;
  records: number;
  latest_price: number | null;
  data: OhlcvPoint[];
}

export interface IndicatorsResponse {
  price: number;
  indicators: Record<string, number>;
  summary: string;
  unavailable?: boolean;
}

export interface SignalData {
  signal: string;
  score: number;
  confidence: number;
  reasons: string[];
  stop_loss: number;
  take_profit: number;
}

export interface SignalResponse {
  signal: SignalData;
  summary: string;
  unavailable?: boolean;
}

export interface PredictionPoint {
  ds: string;
  yhat: number;
  yhat_lower: number;
  yhat_upper: number;
}

export interface HistoryPoint {
  ds: string;
  close: number;
}

export interface PredictionResponse {
  prediction: PredictionPoint[];
  history: HistoryPoint[];
  trend: string;
  summary: string;
  disclaimer?: string;
  unavailable?: boolean;
}

export interface MacroDataset {
  records: number;
  columns: string[];
  data: Record<string, unknown>[];
}

export interface MacroResponse {
  realtime: MacroDataset;
  official: MacroDataset;
}

export interface NewsItem {
  title: string;
  link?: string;
  source?: string;
  published?: string;
  published_date?: string;
  sentiment_score: number;
  sentiment_label: string;
}

export interface NewsResponse {
  total: number;
  avg_sentiment: number;
  label: string;
  news: NewsItem[];
}

export interface DebateResponse {
  summary: string;
  detail: {
    bull: Record<string, unknown> | null;
    bear: Record<string, unknown> | null;
    audit: Record<string, unknown> | null;
    verdict: Record<string, unknown> | null;
  };
}

export interface StrategiesResponse {
  strategies: string[];
  note?: string;
}

export interface BacktestResult {
  strategy: string;
  initial_cash: number;
  final_value: number;
  total_return: string;
  max_drawdown: string;
  sharpe_ratio: number;
  trades: number;
  winning_trades: number;
  win_rate: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  timestamp: string;
  services: Record<string, string>;
  websocket: Record<string, unknown>;
  config: Record<string, string>;
}

export interface StatsResponse {
  websocket: Record<string, unknown>;
  system: {
    uptime: string;
    version: string;
  };
  cache: Record<string, number>;
}

export interface QuickAnalysisResponse {
  signal: SignalData;
  indicators: string;
}

/* ─── Extra Data (补充数据) ─── */

export interface ExtraDataItem {
  records: number;
  data: Record<string, unknown>[];
  _status?: string;
  _error?: string;
}

export interface ChinaMacroItem {
  records: number;
  data: Record<string, unknown>[];
  _status?: string;
}

export interface ExtraDataResponse {
  central_bank: ExtraDataItem;
  cot: ExtraDataItem;
  etf_flow: ExtraDataItem;
  geopol: ExtraDataItem;
  fedwatch: ExtraDataItem;
  china_macro: Record<string, ChinaMacroItem>;
  aisc: ExtraDataItem;
}

/* ─── Calendar (财经日历) ─── */

export interface CalendarEvent {
  date: string;
  event: string;
  importance: string;
  type: string;
  color: string;
  type_label: string;
}

export interface NextCalendarEvent {
  date: string;
  event: string;
  type: string;
  type_label: string;
  importance: string;
  color: string;
}

/* ─── Key Factors (关键因子) ─── */

export interface FactorItem {
  managed_money_long?: number;
  managed_money_short?: number;
  long_short_ratio?: number;
  meeting_date?: string;
  rate?: string;
  hike_probability?: number;
  cut_probability?: number;
  no_change_probability?: number;
  total_reserves_tonnes?: number;
  countries_count?: number;
  top_countries?: { country: string; gold_reserves_tonnes: number }[];
  tips_yield?: number;
  dxy?: number;
  label?: string;
}

export interface FactorsResponse {
  cot: FactorItem | null;
  fedwatch: FactorItem | null;
  central_bank: FactorItem | null;
  tips: FactorItem | null;
  dxy: FactorItem | null;
}

export interface CalendarResponse {
  records: number;
  next_event: NextCalendarEvent | null;
  data: CalendarEvent[];
  error?: string;
}
