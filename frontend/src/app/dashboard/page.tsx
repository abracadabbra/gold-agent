'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import Link from 'next/link';
import { api, useWebSocket } from '@/lib/api';
import type { DebateResponse, BacktestResult, GoldPriceResponse, IndicatorsResponse, OhlcvPoint } from '@/lib/types';
import {
  Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, AreaChart, Area,
} from 'recharts';
import { createChart, ColorType, CrosshairMode, CandlestickSeries, LineSeries, HistogramSeries } from 'lightweight-charts';

/* ─── Shared UI ─── */

function SectionCard({
  title, children, delay = 0, className = '',
}: {
  title: string | React.ReactNode;
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <section
      className={`paper-card reveal-card p-5 md:p-6 ${className}`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <h2 className="section-title">{title}</h2>
      <div className="mt-4 text-[15px] leading-8 text-[var(--foreground)]">{children}</div>
    </section>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      <div className="h-4 bg-[var(--border)] rounded w-3/4" />
      <div className="h-4 bg-[var(--border)] rounded w-1/2" />
      <div className="h-4 bg-[var(--border)] rounded w-5/6" />
    </div>
  );
}

function ErrorCard({ title, error, delay, onRetry, className = '' }: {
  title: string;
  error: string;
  delay: number;
  onRetry: () => void;
  className?: string;
}) {
  return (
    <SectionCard title={title} delay={delay} className={className}>
      <p className="text-[var(--danger)]">{error}</p>
      <button
        onClick={onRetry}
        className="mt-3 data-pill cursor-pointer hover:border-[var(--accent)] transition-colors"
      >
        重试
      </button>
    </SectionCard>
  );
}

function MetricBadge({ label, value, color, children }: {
  label: string;
  value: string;
  color?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-sm muted-copy">{children}{label}</span>
      <span className="font-medium" style={color ? { color } : undefined}>{value}</span>
    </div>
  );
}

function DataTable({ columns, rows }: { columns: string[]; rows: Record<string, unknown>[] }) {
  if (!rows.length) return <p className="muted-copy">无数据</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)]">
            {columns.map(col => (
              <th key={col} className="text-left py-2 pr-4 font-medium muted-copy text-xs uppercase tracking-wider">{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-[var(--border)] last:border-0">
              {columns.map(col => (
                <td key={col} className="py-1.5 pr-4 whitespace-nowrap">
                  {row[col] != null ? String(row[col]) : '-'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CollapseSection({ label, defaultOpen = false, children }: {
  label: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-[var(--border)] rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-left text-sm font-medium hover:bg-[rgba(255,253,247,0.5)] transition-colors"
      >
        {label}
        <span className={`transition-transform ${open ? 'rotate-180' : ''}`}>▾</span>
      </button>
      {open && <div className="px-4 pb-3">{children}</div>}
    </div>
  );
}

/* ─── Hook ─── */

function useApi<T>(fetcher: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fetcherRef = useRef(fetcher);

  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  const execute = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setLoading(true);
    }
    setError(null);
    try {
      setData(await fetcherRef.current());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  return { data, loading, error, execute };
}

/* ─── Cards ─── */

function SystemStatusCard({ refreshKey }: { refreshKey: number }) {
  const { data: health, loading: hl, error: he, execute: re } = useApi(() => api.health());
  const { data: stats, loading: sl, error: se, execute: rs } = useApi(() => api.stats());
  const loading = hl || sl;
  const error = he || se;
  useEffect(() => { re(); rs(); }, [re, rs, refreshKey]);

  if (loading) return <SectionCard title="系统状态" delay={40}><LoadingSkeleton /></SectionCard>;
  if (error || !health) return <ErrorCard title="系统状态" error={error || '无数据'} delay={40} onRetry={() => { re(); rs(); }} />;

  return (
    <SectionCard title="系统状态" delay={40}>
      <div className="flex flex-wrap gap-x-8 gap-y-2">
        <MetricBadge label="状态" value={health.status}>
          <span className="inline-block w-2.5 h-2.5 rounded-full mr-1.5" style={{ backgroundColor: health.status === 'ok' ? '#22c55e' : 'var(--danger)' }} />
        </MetricBadge>
        <MetricBadge label="版本" value={`v${health.version}`} />
        <MetricBadge label="运行时间" value={stats?.system.uptime || '-'} />
        <MetricBadge label="WebSocket 连接" value={String(health.websocket?.total_connections ?? 0)} />
        <MetricBadge label="LLM 模型" value={health.config?.llm_model_bull || '-'} />
        <div className="flex items-baseline gap-2">
          <span className="text-sm muted-copy">缓存</span>
          <span className="text-xs muted-copy">
            {stats?.cache ? Object.entries(stats.cache).map(([k, v]) => `${k}=${v}`).join(', ') : '-'}
          </span>
        </div>
      </div>
    </SectionCard>
  );
}

function PriceChartCard({ refreshKey }: { refreshKey: number }) {
  // ─── State ───
  const [source, setSource] = useState('intl');
  const [period, setPeriod] = useState('1y');
  const [subTab, setSubTab] = useState('spread');
  const [cache, setCache] = useState<Record<string, GoldPriceResponse>>({});
  const [indCache, setIndCache] = useState<Record<string, IndicatorsResponse>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [localRefresh, setLocalRefresh] = useState(0);

  // ─── Refs ───
  const mainContainerRef = useRef<HTMLDivElement>(null);
  const subContainerRef = useRef<HTMLDivElement>(null);

  const cacheKey = `${source}_${period}`;
  const data = cache[cacheKey];
  const indicators = indCache[cacheKey];

  // ─── Helpers ───
  const calcMA = useCallback((values: number[], maPeriod: number): (number | null)[] => {
    const result: (number | null)[] = [];
    for (let i = 0; i < values.length; i++) {
      if (i < maPeriod - 1) { result.push(null); continue; }
      let s = 0;
      for (let j = i - maPeriod + 1; j <= i; j++) s += values[j];
      result.push(s / maPeriod);
    }
    return result;
  }, []);

  const computeStats = useCallback((d: GoldPriceResponse) => {
    const prices = d.data.filter((p): p is OhlcvPoint & { close: number } => p.close != null);
    if (!prices.length) return null;
    const latest = prices[prices.length - 1].close;
    const prev = prices.length > 1 ? prices[prices.length - 2].close : latest;
    const change = latest - prev;
    const changePct = prev !== 0 ? (change / prev) * 100 : 0;
    let high = -Infinity, low = Infinity;
    for (const p of prices) {
      if (p.high != null && p.high > high) high = p.high;
      if (p.low != null && p.low < low) low = p.low;
    }
    return { latest, change, changePct, high, low };
  }, []);

  // ─── Fetch gold data ───
  useEffect(() => {
    let cancelled = false;
    const key = `${source}_${period}`;

    api.gold(source, period)
      .then(r => { if (!cancelled) { setCache(prev => ({ ...prev, [key]: r })); setLoading(false); } })
      .catch(e => { if (!cancelled) { setError(e instanceof Error ? e.message : '未知错误'); setLoading(false); } });

    return () => { cancelled = true; };
  }, [source, period, refreshKey, localRefresh]);

  // ─── Fetch indicators ───
  useEffect(() => {
    let cancelled = false;
    const key = `${source}_${period}`;
    api.indicators(source, period)
      .then(r => { if (!cancelled) setIndCache(prev => ({ ...prev, [key]: r })); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [source, period]);

  // ─── Pre-fetch alternate source for spread sub-chart ───
  useEffect(() => {
    if (subTab !== 'spread') return;
    let cancelled = false;
    const sources = source === 'intl' ? ['shfe'] : source === 'shfe' ? ['intl'] : ['intl', 'shfe'];
    for (const s of sources) {
      const k = `${s}_${period}`;
      if (cache[k]) continue;
      api.gold(s, period)
        .then(r => { if (!cancelled) setCache(prev => ({ ...prev, [k]: r })); })
        .catch(() => {});
    }
    return () => { cancelled = true; };
  }, [subTab, source, period, refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Main chart ───
  useEffect(() => {
    if (!data || !mainContainerRef.current || loading) return;

    const container = mainContainerRef.current;
    const fmtDate = (t: unknown) => {
      const s = String(t);
      return s.length >= 10 ? s.slice(0, 10) : s;
    };
    const chart = createChart(container, {
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#7f6d5a' },
      grid: { vertLines: { color: 'rgba(191,166,130,0.15)' }, horzLines: { color: 'rgba(191,166,130,0.15)' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: 'rgba(191,166,130,0.3)' },
      timeScale: {
        borderColor: 'rgba(191,166,130,0.3)',
        timeVisible: false,
        tickMarkFormatter: (t: unknown) => {
          const s = String(t);
          return s.length >= 10 ? s.slice(5, 10) : s;
        },
      },
      localization: {
        timeFormatter: fmtDate,
        dateFormat: 'yyyy-MM-dd',
      },
      width: container.clientWidth,
      height: 380,
    });

    const validData = data.data.filter((d): d is OhlcvPoint & { close: number } => d.close != null);
    if (!validData.length) { chart.remove(); return; }

    const times = validData.map(d => d.date.slice(0, 10));
    const closes = validData.map(d => d.close);

    // Candlestick series
    const candle = chart.addSeries(CandlestickSeries, {
      upColor: '#ef4444', downColor: '#22c55e',
      borderUpColor: '#ef4444', borderDownColor: '#22c55e',
      wickUpColor: '#ef4444', wickDownColor: '#22c55e',
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    });
    candle.setData(validData.map(d => ({
      time: d.date.slice(0, 10),
      open: d.open ?? d.close,
      high: d.high ?? d.close,
      low: d.low ?? d.close,
      close: d.close,
    })));

    // Volume histogram
    const vol = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol-scale',
    });
    chart.priceScale('vol-scale').applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
    });
    vol.setData(validData.map(d => ({
      time: d.date.slice(0, 10),
      value: d.volume ?? 0,
      color: d.close >= (d.open ?? d.close) ? 'rgba(239,68,68,0.3)' : 'rgba(34,197,94,0.3)',
    })));

    // Moving averages
    const maColors = [
      { period: 20, color: '#3b82f6' },
      { period: 50, color: '#f59e0b' },
      { period: 200, color: '#8b5cf6' },
    ];
    for (const ma of maColors) {
      const vals = calcMA(closes, ma.period);
      const maData = vals.map((v, i) => v != null ? { time: times[i], value: v } : null).filter(Boolean);
      if (maData.length > 0) {
        const line = chart.addSeries(LineSeries, {
          color: ma.color, lineWidth: 1, lastValueVisible: false,
          priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
        });
        line.setData(maData as Array<{ time: string; value: number }>);
      }
    }

    chart.timeScale().fitContent();

    // Resize observer
    const observer = new ResizeObserver(entries => {
      for (const e of entries) chart.applyOptions({ width: e.contentRect.width });
    });
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.remove();
    };
  }, [data, loading, calcMA]);

  // ─── Sub chart (spread) ───
  useEffect(() => {
    // Only render spread chart
    if (subTab !== 'spread' || !subContainerRef.current) {
      return;
    }

    const intlData = source === 'intl' ? data : cache[`intl_${period}`];
    const shfeData = source === 'shfe' ? data : cache[`shfe_${period}`];

    if (!intlData || !intlData.data.length) return;

    const container = subContainerRef.current;
    const chart = createChart(container, {
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#7f6d5a' },
      grid: { vertLines: { color: 'rgba(191,166,130,0.15)' }, horzLines: { color: 'rgba(191,166,130,0.15)' } },
      rightPriceScale: { borderColor: 'rgba(191,166,130,0.3)' },
      timeScale: {
        borderColor: 'rgba(191,166,130,0.3)',
        tickMarkFormatter: (t: unknown) => {
          const s = String(t);
          return s.length >= 10 ? s.slice(5, 10) : s;
        },
      },
      localization: {
        timeFormatter: (t: unknown) => {
          const s = String(t);
          return s.length >= 10 ? s.slice(0, 10) : s;
        },
        dateFormat: 'yyyy-MM-dd',
      },
      width: container.clientWidth,
      height: 180,
    });

    const intlLine = chart.addSeries(LineSeries, {
      color: '#3b82f6', lineWidth: 2, lastValueVisible: true,
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    });
    intlLine.setData(
      intlData.data
        .filter((d): d is OhlcvPoint & { close: number } => d.close != null)
        .map(d => ({ time: d.date.slice(0, 10), value: d.close }))
    );

    if (shfeData && shfeData.data.length > 0) {
      const shfeLine = chart.addSeries(LineSeries, {
        color: '#f59e0b', lineWidth: 2, lastValueVisible: true,
        priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
      });
      shfeLine.setData(
        shfeData.data
          .filter((d): d is OhlcvPoint & { close: number } => d.close != null)
          .map(d => ({ time: d.date.slice(0, 10), value: d.close }))
      );
    }

    chart.timeScale().fitContent();

    const observer = new ResizeObserver(entries => {
      for (const e of entries) chart.applyOptions({ width: e.contentRect.width });
    });
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.remove();
    };
  }, [subTab, data, cache, source, period]);

  // ─── Decide what to show ───
  const stats = useMemo(() => data ? computeStats(data) : null, [data, computeStats]);

  if (loading && !data) {
    return <SectionCard title="行情数据" delay={90} className="md:col-span-2 xl:col-span-3"><LoadingSkeleton /></SectionCard>;
  }
  if (error && !data) {
    return (
      <ErrorCard title="行情数据" error={error} delay={90} onRetry={() => {
        const key = `${source}_${period}`;
        setLoading(true);
        setError(null);
        api.gold(source, period)
          .then(r => { setCache(prev => ({ ...prev, [key]: r })); setLoading(false); })
          .catch(e => { setError(e instanceof Error ? e.message : '未知错误'); setLoading(false); });
      }} className="md:col-span-2 xl:col-span-3" />
    );
  }
  if (!data || !data.data.length) {
    return <SectionCard title="行情数据" delay={90} className="md:col-span-2 xl:col-span-3"><p className="muted-copy">无数据</p></SectionCard>;
  }

  return (
    <SectionCard title="行情数据" delay={90} className="md:col-span-2 xl:col-span-3">
      {/* Refresh button */}
      <div className="flex items-center justify-end gap-2 -mt-2 mb-1">
        {loading && data && (
          <span className="flex items-center gap-1 text-xs muted-copy">
            <span className="inline-block w-2 h-2 border border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
            刷新中
          </span>
        )}
        <button
          onClick={() => { setLoading(true); setError(null); setLocalRefresh(k => k + 1); }}
          className="data-pill cursor-pointer text-xs hover:border-[var(--accent)] transition-colors"
        >
          刷新
        </button>
      </div>
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div className="flex gap-1.5 flex-wrap">
          {[['intl', '国际'], ['gld', 'GLD'], ['shfe', '沪金']].map(([val, label]) => (
            <button
              key={val}
              onClick={() => { if (source !== val) { setSource(val); setLoading(true); } }}
              className={`data-pill cursor-pointer transition-colors text-xs ${source === val ? 'border-[var(--accent)] text-[var(--accent)]' : ''}`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {[['1mo', '1月'], ['3mo', '3月'], ['6mo', '6月'], ['1y', '1年'], ['5y', '5年']].map(([val, label]) => (
            <button
              key={val}
              onClick={() => { if (period !== val) { setPeriod(val); setLoading(true); } }}
              className={`data-pill cursor-pointer transition-colors text-xs ${period === val ? 'border-[var(--accent)] text-[var(--accent)]' : ''}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="flex flex-wrap items-baseline gap-3 mb-3">
          <span className="metric-value text-[var(--accent)]">{stats.latest.toFixed(2)}</span>
          <span className={`text-sm font-medium ${stats.change >= 0 ? 'text-[#ef4444]' : 'text-[#22c55e]'}`}>
            {stats.change >= 0 ? '+' : ''}{stats.change.toFixed(2)} ({stats.changePct >= 0 ? '+' : ''}{stats.changePct.toFixed(2)}%)
          </span>
          <span className="text-xs muted-copy">高: {stats.high.toFixed(2)} / 低: {stats.low.toFixed(2)}</span>
          <span className="text-xs muted-copy">{data.records} 条记录</span>
        </div>
      )}

      {/* Main chart */}
      <div ref={mainContainerRef} className="w-full" style={{ height: 380 }} />

      {/* Sub chart */}
      <div className="mt-4">
        <div className="flex gap-1.5 mb-2 flex-wrap items-center">
          {[['spread', '价差'], ['rsi', 'RSI'], ['macd', 'MACD'], ['bb', '布林带']].map(([val, label]) => (
            <div key={val} className="flex items-center gap-1">
              <button
                onClick={() => setSubTab(val)}
                className={`data-pill cursor-pointer transition-colors text-xs ${subTab === val ? 'border-[var(--accent)] text-[var(--accent)]' : ''}`}
              >
                {label}
              </button>
              <span className="relative group">
                <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-[var(--muted)] text-[10px] cursor-help text-[var(--muted)] leading-none">?</span>
                <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 rounded-lg text-xs whitespace-nowrap bg-[var(--foreground)] text-[var(--background)] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-lg">
                  {SUB_TAB_HELP[val]}
                </span>
              </span>
            </div>
          ))}
        </div>
        <div className="w-full min-h-[180px]">
          {subTab === 'spread' && (
            <div ref={subContainerRef} className="w-full" style={{ height: 180 }} />
          )}
          {subTab === 'rsi' && <RsiGauge ind={indicators?.indicators ?? {}} />}
          {subTab === 'macd' && <MacdGauge ind={indicators?.indicators ?? {}} />}
          {subTab === 'bb' && <BbGauge ind={indicators?.indicators ?? {}} price={stats?.latest ?? 0} />}
        </div>
        {/* Raw indicator summary */}
        {indicators?.summary && (
          <details className="mt-3">
            <summary className="text-sm cursor-pointer muted-copy hover:text-[var(--accent)]">查看详情</summary>
            <pre className="mt-2 text-xs whitespace-pre-wrap text-[var(--muted)] leading-6">{indicators.summary}</pre>
          </details>
        )}
      </div>
    </SectionCard>
  );
}

function signalLabel(s: string) {
  const map: Record<string, string> = { strong_buy: '强烈买入', buy: '买入', neutral: '中性', sell: '卖出', strong_sell: '强烈卖出' };
  return map[s] || s;
}

function signalTone(s: string) {
  if (s === 'strong_buy' || s === 'buy') return 'var(--accent)';
  if (s === 'strong_sell' || s === 'sell') return 'var(--danger)';
  return 'var(--muted)';
}

function SignalGaugeCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.signal());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading && !data) return <SectionCard title="交易信号" delay={130}><LoadingSkeleton /></SectionCard>;
  if (error && !data) return <ErrorCard title="交易信号" error={error || '无数据'} delay={130} onRetry={execute} />;
  if (!data) return <SectionCard title="交易信号" delay={130}><LoadingSkeleton /></SectionCard>;

  const sig = data.signal;
  const tone = signalTone(sig.signal);
  const pct = Math.min(100, Math.max(0, ((sig.score + 100) / 200) * 100));

  return (
    <SectionCard title="交易信号" delay={130}>
      {loading && (
        <div className="flex items-center gap-1.5 -mt-1 mb-2">
          <span className="inline-block w-3 h-3 border border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
          <span className="text-xs muted-copy">刷新中</span>
        </div>
      )}
      <p className="text-2xl font-display mb-2" style={{ color: tone }}>{signalLabel(sig.signal)}</p>

      {/* Score gauge bar */}
      <div className="relative mb-1">
        <div className="h-3 rounded-full" style={{
          background: 'linear-gradient(to right, #e74c3c, #e8a87c, #95a5a6, #a8d8a8, #27ae60)',
        }} />
        <div className="flex justify-between text-xs muted-copy mt-0.5">
          <span>-100</span>
          <span>0</span>
          <span>+100</span>
        </div>
        {/* Pointer triangle */}
        <div className="absolute -top-1 transform -translate-x-1/2 transition-all duration-500" style={{ left: `${pct}%` }}>
          <div className="w-0 h-0 border-l-[8px] border-r-[8px] border-t-[10px] border-l-transparent border-r-transparent" style={{ borderTopColor: tone }} />
        </div>
      </div>

      <div className="space-y-1">
        <MetricBadge label="评分" value={`${sig.score} / 100`} />
        <MetricBadge label="置信度" value={`${(sig.confidence * 100).toFixed(0)}%`} />
        {sig.stop_loss && <MetricBadge label="止损" value={sig.stop_loss.toFixed(2)} />}
        {sig.take_profit && <MetricBadge label="止盈" value={sig.take_profit.toFixed(2)} />}
      </div>

      {sig.reasons?.length > 0 && (
        <ul className="report-list mt-3 space-y-0.5 text-sm">
          {sig.reasons.map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      )}
    </SectionCard>
  );
}

function RsiGauge({ ind }: { ind: Record<string, number> }) {
  const rsi = ind.rsi14;
  if (rsi == null) return <p className="muted-copy">RSI 数据不可用</p>;
  const pct = Math.min(100, Math.max(0, (rsi / 100) * 100));
  const color = rsi < 30 ? 'var(--danger)' : rsi > 70 ? 'var(--accent)' : 'var(--muted)';
  return (
    <div>
      <p className="text-lg font-medium mb-1">RSI: <span style={{ color }}>{rsi.toFixed(2)}</span></p>
      <div className="relative h-4 rounded-full overflow-hidden border border-[var(--border)]"
        style={{ background: 'linear-gradient(to right, #ef4444, #fef3c7, #22c55e)' }}>
        <div className="absolute top-0 bottom-0 w-0.5 bg-gray-500 z-10" style={{ left: '30%' }} />
        <div className="absolute top-0 bottom-0 w-0.5 bg-gray-500 z-10" style={{ left: '70%' }} />
        <div className="absolute top-0 bottom-0 w-[3px] bg-[var(--foreground)] z-20 transition-all duration-500 rounded-full"
          style={{ left: `${pct}%`, transform: 'translateX(-50%)' }} />
      </div>
      <div className="flex justify-between text-xs muted-copy mt-0.5">
        <span>0</span>
        <span>30 超卖</span>
        <span>70 超买</span>
        <span>100</span>
      </div>
    </div>
  );
}

function MacdGauge({ ind }: { ind: Record<string, number> }) {
  const line = ind.macd_line;
  const signal = ind.macd_signal;
  const hist = ind.macd_histogram;
  if (line == null && signal == null && hist == null) return <p className="muted-copy">MACD 数据不可用</p>;
  return (
    <div className="space-y-3">
      {line != null && (
        <div className="flex justify-between items-center p-2 rounded-lg border border-[var(--border)]">
          <span className="muted-copy">MACD 线</span>
          <span className="font-medium">{line.toFixed(4)}</span>
        </div>
      )}
      {signal != null && (
        <div className="flex justify-between items-center p-2 rounded-lg border border-[var(--border)]">
          <span className="muted-copy">信号线</span>
          <span className="font-medium">{signal.toFixed(4)}</span>
        </div>
      )}
      {hist != null && (
        <div>
          <div className="flex justify-between items-center mb-1">
            <span className="muted-copy">柱状图</span>
            <span className="font-medium" style={{ color: hist >= 0 ? '#22c55e' : '#ef4444' }}>{hist.toFixed(4)}</span>
          </div>
          <div className="relative h-1.5 rounded-full overflow-hidden bg-gray-200">
            <div className="absolute top-0 bottom-0 left-1/2 w-0.5 bg-gray-400" />
            <div className="absolute top-0 bottom-0 rounded-full transition-all" style={{
              width: `${Math.min(100, Math.abs(hist) * 2000)}%`,
              maxWidth: '45%',
              left: hist >= 0 ? '50%' : undefined,
              right: hist < 0 ? '50%' : undefined,
              backgroundColor: hist >= 0 ? '#22c55e' : '#ef4444',
            }} />
          </div>
        </div>
      )}
    </div>
  );
}

function BbGauge({ ind, price }: { ind: Record<string, number>; price: number }) {
  const upper = ind.bb_upper;
  const middle = ind.bb_mid;
  const lower = ind.bb_lower;
  if (upper == null || middle == null || lower == null) return <p className="muted-copy">布林带数据不可用</p>;
  const range = upper - lower;
  const position = range > 0 ? ((price - lower) / range) * 100 : 50;
  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center p-2 rounded-lg border border-[var(--border)]">
        <span className="muted-copy">上轨</span>
        <span className="font-medium">{upper.toFixed(2)}</span>
      </div>
      <div className="flex justify-between items-center p-2 rounded-lg border border-[var(--accent-soft)]">
        <span className="muted-copy">中轨 (均线)</span>
        <span className="font-medium text-[var(--accent)]">{middle.toFixed(2)}</span>
      </div>
      <div className="flex justify-between items-center p-2 rounded-lg border border-[var(--border)]">
        <span className="muted-copy">下轨</span>
        <span className="font-medium">{lower.toFixed(2)}</span>
      </div>
      <div>
        <div className="flex justify-between text-xs muted-copy mb-1">
          <span>下轨</span>
          <span>位置: {position.toFixed(1)}%</span>
          <span>上轨</span>
        </div>
        <div className="relative h-4 rounded-full overflow-hidden border border-[var(--border)]"
          style={{ background: 'linear-gradient(to right, #3b82f6, #22c55e, #ef4444)' }}>
          <div className="absolute top-0 bottom-0 w-[3px] bg-[var(--foreground)] z-10 rounded-full transition-all duration-500"
            style={{ left: `${Math.min(100, Math.max(0, position))}%`, transform: 'translateX(-50%)' }} />
        </div>
      </div>
    </div>
  );
}

function PredictionChartCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.prediction());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="价格预测" delay={210}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="价格预测" error={error || '无数据'} delay={210} onRetry={execute} />;

  if (!data.prediction.length) return <SectionCard title="价格预测" delay={210}><p className="muted-copy">无数据</p></SectionCard>;

  const combined = [
    ...(data.history || []).map(h => ({ ...h, yhat: null as number | null, yhat_lower: null as number | null, yhat_upper: null as number | null })),
    ...data.prediction.map(p => ({ ...p, close: null as number | null })),
  ];

  return (
    <SectionCard title={<span className="flex items-center gap-1.5">价格预测<span className="relative group"><span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-[var(--muted)] text-[10px] cursor-help text-[var(--muted)] leading-none">?</span><span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 rounded-lg text-xs whitespace-nowrap bg-[var(--foreground)] text-[var(--background)] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-lg">{PREDICTION_HELP}</span></span></span>} delay={210}>
      <div className="flex items-center gap-3 mb-3">
        <span className="data-pill">趋势: {data.trend === 'up' ? '↑ 上涨' : data.trend === 'down' ? '↓ 下跌' : '→ 震荡'}</span>
        <span className="data-pill">预测: {data.prediction.length}天</span>
        <span className="data-pill">历史: {data.history?.length || 0}天</span>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={combined}>
          <defs>
            <linearGradient id="bandGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#d4a849" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#d4a849" stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="ds" tick={{ fontSize: 12 }} stroke="var(--muted)" />
          <YAxis stroke="var(--muted)" tick={{ fontSize: 12 }} domain={['auto', 'auto']} />
          <Tooltip
            contentStyle={{ background: 'var(--surface-strong)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 13 }}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            formatter={(value: any, name: any) => {
              const labels: Record<string, string> = { close: '收盘价', yhat: '预测值', yhat_lower: '下限', yhat_upper: '上限' };
              if (value === null) return [null];
              return [Number(value).toFixed(2), labels[name] || name];
            }}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            labelFormatter={(label: any) => `日期: ${label}`}
          />
          <Area type="monotone" dataKey="yhat_upper" fill="url(#bandGrad)" stroke="none" connectNulls={false} />
          <Area type="monotone" dataKey="yhat_lower" fill="var(--surface-strong)" stroke="none" connectNulls={false} />
          <Line type="monotone" dataKey="yhat" stroke="#d4a849" strokeWidth={2} dot={false} connectNulls={false} />
          <Line type="monotone" dataKey="close" stroke="#4a9eff" strokeWidth={1.5} dot={false} connectNulls={false} />
        </AreaChart>
      </ResponsiveContainer>
      {data.summary && (
        <details className="mt-3">
          <summary className="text-sm cursor-pointer muted-copy hover:text-[var(--accent)]">查看分析文本</summary>
          <pre className="mt-2 text-xs whitespace-pre-wrap text-[var(--muted)] leading-6">{data.summary}</pre>
        </details>
      )}
    </SectionCard>
  );
}

function MacroCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.macro());
  useEffect(() => { execute(); }, [execute, refreshKey]);
  const [tab, setTab] = useState<'realtime' | 'official'>('realtime');

  if (loading) return <SectionCard title="宏观数据" delay={250}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="宏观数据" error={error || '无数据'} delay={250} onRetry={execute} />;

  const ds = data[tab];

  return (
    <SectionCard title="宏观数据" delay={250}>
      <div className="flex gap-2 mb-3">
        <button
          onClick={() => setTab('realtime')}
          className={`data-pill cursor-pointer transition-colors ${tab === 'realtime' ? 'border-[var(--accent)] text-[var(--accent)]' : ''}`}
        >
          实时 ({data.realtime.records})
        </button>
        <button
          onClick={() => setTab('official')}
          className={`data-pill cursor-pointer transition-colors ${tab === 'official' ? 'border-[var(--accent)] text-[var(--accent)]' : ''}`}
        >
          官方 ({data.official.records})
        </button>
      </div>
      <DataTable columns={ds.columns} rows={ds.data.slice(-10)} />
    </SectionCard>
  );
}

function sentimentLabel(label: string) {
  if (label === 'bullish') return '看多';
  if (label === 'bearish') return '看空';
  return '中性';
}

function NewsCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.news());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="新闻情绪" delay={290}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="新闻情绪" error={error || '无数据'} delay={290} onRetry={execute} />;

  return (
    <SectionCard title="新闻情绪" delay={290}>
      <div className="flex flex-wrap gap-2 mb-3">
        <span className="data-pill">总数: {data.total}</span>
        <span className="data-pill">平均: {data.avg_sentiment.toFixed(3)}</span>
        <span
          className="data-pill"
          style={{ color: data.label === 'bullish' ? 'var(--accent)' : data.label === 'bearish' ? 'var(--danger)' : 'var(--muted)' }}
        >
          {sentimentLabel(data.label)}
        </span>
      </div>
      <div className="space-y-2 max-h-80 overflow-y-auto">
        {data.news.map((item, i) => (
          <div key={i} className="p-3 rounded-xl border border-[var(--border)] text-sm">
            <div className="flex items-start justify-between gap-2">
              <span className="flex-1">
                {item.link ? (
                  <a href={item.link} target="_blank" rel="noopener noreferrer" className="inline-link">{item.title}</a>
                ) : item.title}
              </span>
              <span
                className="text-xs whitespace-nowrap px-2 py-0.5 rounded-full"
                style={{
                  backgroundColor: item.sentiment_label === 'bullish' ? 'rgba(182,122,40,0.12)' : item.sentiment_label === 'bearish' ? 'rgba(197,75,66,0.12)' : 'rgba(127,109,90,0.12)',
                  color: item.sentiment_label === 'bullish' ? 'var(--accent)' : item.sentiment_label === 'bearish' ? 'var(--danger)' : 'var(--muted)',
                }}
              >
                {sentimentLabel(item.sentiment_label)}
              </span>
            </div>
            {item.source && <p className="muted-copy text-xs mt-1">{item.source}</p>}
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

/* ─── Cards with manual trigger ─── */

function DebateCard() {
  const [data, setData] = useState<DebateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    setData(null);
    try {
      setData(await api.debate());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const roleLabel: Record<string, string> = { bull: '看多方', bear: '看空方', audit: '数据审计', verdict: '最终裁决' };
  const roleColor: Record<string, string> = { bull: '#22c55e', bear: 'var(--danger)', audit: '#3b82f6', verdict: 'var(--accent)' };

  return (
    <SectionCard title="辩论引擎" delay={330}>
      <div className="flex items-center gap-3 mb-3">
        <button
          onClick={run}
          disabled={loading}
          className="data-pill cursor-pointer hover:border-[var(--accent)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? '辩论进行中...' : '运行辩论'}
        </button>
        {loading && (
          <div className="flex items-center gap-1.5 text-sm muted-copy">
            <span className="inline-block w-4 h-4 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
            4 阶段进行中...
          </div>
        )}
      </div>

      {error && <p className="text-[var(--danger)] mb-3">{error}</p>}

      {data && (
        <div className="space-y-2">
          {data.summary && (
            <pre className="text-xs whitespace-pre-wrap text-[var(--muted)] leading-6 mb-3 p-3 rounded-xl bg-[rgba(255,253,247,0.4)] border border-[var(--border)]">
              {data.summary}
            </pre>
          )}
          {Object.entries(roleLabel).map(([key, label]) => {
            const roleData = data.detail[key as keyof typeof data.detail];
            if (!roleData) return null;
            return (
              <CollapseSection
                key={key}
                label={
                  <span style={{ color: roleColor[key] }}>{label}</span>
                }
              >
                <pre className="text-xs whitespace-pre-wrap leading-6">{JSON.stringify(roleData, null, 2)}</pre>
              </CollapseSection>
            );
          })}
        </div>
      )}
    </SectionCard>
  );
}

function BacktestCard({ refreshKey }: { refreshKey: number }) {
  const { data: strategies, loading: sl, execute: fetchStrategies } = useApi(() => api.strategies());
  useEffect(() => { fetchStrategies(); }, [fetchStrategies, refreshKey]);
  const [selectedStrategy, setSelectedStrategy] = useState('golden_cross');
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const run = async () => {
    setRunning(true);
    setRunError(null);
    setResult(null);
    try {
      setResult(await api.backtest(selectedStrategy));
    } catch (e) {
      setRunError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setRunning(false);
    }
  };

  return (
    <SectionCard title="回测" delay={370}>
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <select
          value={selectedStrategy}
          onChange={e => setSelectedStrategy(e.target.value)}
          className="data-pill bg-transparent cursor-pointer text-sm"
          disabled={sl}
        >
          {strategies?.strategies.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <button
          onClick={run}
          disabled={running}
          className="data-pill cursor-pointer hover:border-[var(--accent)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {running ? '回测中...' : '运行回测'}
        </button>
      </div>

      {runError && <p className="text-[var(--danger)] mb-2">{runError}</p>}

      {result && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <MetricBadge label="收益率" value={result.total_return} color={result.total_return.startsWith('-') ? 'var(--danger)' : 'var(--accent)'} />
          <MetricBadge label="夏普比率" value={result.sharpe_ratio.toFixed(2)} />
          <MetricBadge label="最大回撤" value={result.max_drawdown} />
          <MetricBadge label="交易次数" value={String(result.trades)} />
          <MetricBadge label="胜率" value={result.win_rate} />
          <MetricBadge label="最终资金" value={`$${result.final_value.toLocaleString()}`} />
        </div>
      )}
    </SectionCard>
  );
}

/* ─── Extra Data Cards (数据补充) ─── */

function CentralBankCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.extraData());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="央行黄金储备" delay={410}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="央行黄金储备" error={error || '无数据'} delay={410} onRetry={execute} />;

  const cb = data.central_bank;
  const rows = cb.data as unknown as Record<string, unknown>[];
  const columns = ['country', 'date', 'gold_reserves_tonnes', 'rank'];

  return (
    <SectionCard title="央行黄金储备" delay={410}>
      <div className="flex flex-wrap gap-2 mb-3">
        <span className="data-pill">国家: {new Set(rows.map(r => r.country as string)).size}</span>
        <span className="data-pill">记录: {cb.records}</span>
        {cb._status === 'error' && <span className="data-pill text-[var(--danger)]">部分失败</span>}
      </div>
      <DataTable columns={columns} rows={rows.slice(0, 15)} />
    </SectionCard>
  );
}

function CotCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.extraData());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="COT 持仓" delay={450}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="COT 持仓" error={error || '无数据'} delay={450} onRetry={execute} />;

  const cot = data.cot;
  const rows = cot.data as unknown as Record<string, unknown>[];
  const columns = ['date', 'open_interest', 'managed_money_long', 'managed_money_short', 'producer_long', 'producer_short'];

  return (
    <SectionCard title="COT 持仓" delay={450}>
      <div className="flex flex-wrap gap-2 mb-3">
        <span className="data-pill">记录: {cot.records}</span>
        {cot._status === 'error' && <span className="data-pill text-[var(--danger)]">失败</span>}
      </div>
      <DataTable columns={columns} rows={rows.slice(0, 10)} />
    </SectionCard>
  );
}

function EtfFlowCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.extraData());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="ETF 流量" delay={490}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="ETF 流量" error={error || '无数据'} delay={490} onRetry={execute} />;

  const etf = data.etf_flow;
  const rows = etf.data as unknown as Record<string, unknown>[];
  const columns = ['date', 'fund_name', 'region', 'holdings_tonnes', 'flow_tonnes'];

  return (
    <SectionCard title="ETF 流量" delay={490}>
      <div className="flex flex-wrap gap-2 mb-3">
        <span className="data-pill">记录: {etf.records}</span>
        {etf._status === 'error' && <span className="data-pill text-[var(--danger)]">失败</span>}
      </div>
      <DataTable columns={columns} rows={rows.slice(0, 10)} />
    </SectionCard>
  );
}

function GeopolCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.extraData());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="地缘政治风险" delay={530}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="地缘政治风险" error={error || '无数据'} delay={530} onRetry={execute} />;

  const gp = data.geopol;
  const rows = gp.data as unknown as Record<string, unknown>[];
  const columns = ['date', 'gpr_index', 'gpr_threats', 'gpr_acts'].filter(c => rows.some(r => r[c] != null));

  return (
    <SectionCard title="地缘政治风险" delay={530}>
      <div className="flex flex-wrap gap-2 mb-3">
        <span className="data-pill">记录: {gp.records}</span>
        {gp._status === 'error' && <span className="data-pill text-[var(--danger)]">失败</span>}
      </div>
      <DataTable columns={columns} rows={rows.slice(0, 10)} />
    </SectionCard>
  );
}

function FedWatchCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.extraData());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="FedWatch 利率预期" delay={570}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="FedWatch 利率预期" error={error || '无数据'} delay={570} onRetry={execute} />;

  const fw = data.fedwatch;
  const rows = fw.data as unknown as Record<string, unknown>[];
  const latest = rows[rows.length - 1];

  return (
    <SectionCard title="FedWatch 利率预期" delay={570}>
      <div className="flex flex-wrap gap-2 mb-3">
        <span className="data-pill">会议: {rows.length}</span>
        {fw._status === 'error' && <span className="data-pill text-[var(--danger)]">失败</span>}
      </div>
      {latest && (
        <div className="grid grid-cols-3 gap-3 mb-3">
          <MetricBadge label="降息概率" value={latest.cut_prob != null ? `${(latest.cut_prob as number).toFixed(1)}%` : '-'}
            color="var(--accent)" />
          <MetricBadge label="维持概率" value={latest.hold_prob != null ? `${(latest.hold_prob as number).toFixed(1)}%` : '-'}
            color="var(--muted)" />
          <MetricBadge label="加息概率" value={latest.hike_prob != null ? `${(latest.hike_prob as number).toFixed(1)}%` : '-'}
            color="var(--danger)" />
        </div>
      )}
      <DataTable columns={['meeting_date', 'cut_prob', 'hold_prob', 'hike_prob']} rows={rows.slice(0, 6)} />
    </SectionCard>
  );
}

function ChinaMacroCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.extraData());
  useEffect(() => { execute(); }, [execute, refreshKey]);
  const [tab, setTab] = useState('cpi');

  if (loading) return <SectionCard title="中国宏观数据" delay={610}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="中国宏观数据" error={error || '无数据'} delay={610} onRetry={execute} />;

  const indicators = ['cpi', 'ppi', 'pmi', 'm2', 'gdp', 'lpr', 'usd_cny'];
  const labelMap: Record<string, string> = { cpi: 'CPI', ppi: 'PPI', pmi: 'PMI', m2: 'M2', gdp: 'GDP', lpr: 'LPR', usd_cny: '汇率' };
  const current = data.china_macro[tab];
  const rows = (current?.data || []) as unknown as Record<string, unknown>[];

  return (
    <SectionCard title="中国宏观数据" delay={610}>
      <div className="flex flex-wrap gap-2 mb-3">
        {indicators.map(ind => (
          <button
            key={ind}
            onClick={() => setTab(ind)}
            className={`data-pill cursor-pointer transition-colors text-xs ${tab === ind ? 'border-[var(--accent)] text-[var(--accent)]' : ''}`}
          >
            {labelMap[ind]} ({data.china_macro[ind]?.records ?? 0})
          </button>
        ))}
      </div>
      <p className="text-xs muted-copy mb-2">{labelMap[tab]} — {current?._status === 'error' ? '获取失败' : `${current?.records ?? 0} 条记录`}</p>
      <DataTable columns={['date', 'value']} rows={rows.slice(0, 8)} />
    </SectionCard>
  );
}

function AiscCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.extraData());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="生产成本 AISC" delay={650}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="生产成本 AISC" error={error || '无数据'} delay={650} onRetry={execute} />;

  const aisc = data.aisc;
  const rows = aisc.data as unknown as Record<string, unknown>[];
  const latest = rows[rows.length - 1];

  return (
    <SectionCard title="生产成本 AISC" delay={650}>
      <div className="flex flex-wrap gap-2 mb-3">
        <span className="data-pill">记录: {aisc.records}</span>
        {aisc._status === 'error' && <span className="data-pill text-[var(--danger)]">失败</span>}
      </div>
      {latest && (
        <p className="metric-value text-[var(--accent)] mb-2">
          ${(latest.global_avg_aisc as number)?.toFixed(0) ?? '-'} /oz
          <span className="text-sm muted-copy ml-2">
            {String(latest.year)}-{String(latest.quarter)}
          </span>
        </p>
      )}
      <DataTable columns={['year', 'quarter', 'global_avg_aisc', 'region']} rows={rows.slice(0, 8)} />
    </SectionCard>
  );
}

/* ─── Calendar Card ─── */

function CalendarCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.calendar());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="财经日历" delay={680}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="财经日历" error={error || '无数据'} delay={680} onRetry={execute} />;

  const nextEvent = data.next_event;

  return (
    <SectionCard title="财经日历" delay={680} className="xl:col-span-1">
      {nextEvent && (
        <div
          className="rounded-lg p-4 mb-4 border-l-4"
          style={{ borderLeftColor: nextEvent.color, backgroundColor: `${nextEvent.color}10` }}
        >
          <span className="text-xs muted-copy uppercase tracking-wider">下一重大事件</span>
          <p className="text-lg font-semibold mt-1">{nextEvent.event}</p>
          <div className="flex flex-wrap gap-2 mt-2">
            <span className="data-pill text-xs">{nextEvent.date}</span>
            <span className="data-pill text-xs">{nextEvent.type_label}</span>
          </div>
        </div>
      )}
      <DataTable
        columns={['date', 'event', 'type_label']}
        rows={data.data.map(e => ({
          date: e.date,
          event: e.event,
          type_label: e.type_label,
        }))}
      />
    </SectionCard>
  );
}

/* ─── Page ─── */

const SUB_TAB_HELP: Record<string, string> = {
  spread: '国际金价(蓝)与沪金(橙)走势对比，观察国内外价差',
  rsi: '相对强弱指标(RSI): >70 超买(可能回调), <30 超卖(可能反弹)',
  macd: '指数平滑异同平均线: 快线上穿信号线为买入信号，下穿为卖出信号',
  bb: '布林带: 价格触及上轨可能超买，触及下轨可能超卖; 带宽收窄预示变盘',
};

const PREDICTION_HELP =
  '基于 Prophet 模型的时序预测: 蓝线为历史收盘价，金线为预测中值，金色阴影为 95% 置信区间。预测仅作为趋势参考，不构成投资建议。';

const REFRESH_OPTIONS = [
  { label: '关闭', value: 0 },
  { label: '30s', value: 30_000 },
  { label: '60s', value: 60_000 },
  { label: '120s', value: 120_000 },
];

const SECTIONS = [
  { key: 'market', label: '行情概览' },
  { key: 'macro', label: '宏观数据' },
  { key: 'extra', label: '补充数据' },
  { key: 'tools', label: '工具' },
] as const;

type SectionKey = typeof SECTIONS[number]['key'];

const VISIBLE_KEY = 'dash_visible_cards';

function loadVisible(): Record<string, boolean> {
  if (typeof window === 'undefined') return {};
  try {
    return JSON.parse(localStorage.getItem(VISIBLE_KEY) || '{}');
  } catch { return {}; }
}

function TopMetricsBar({ refreshKey }: { refreshKey: number }) {
  const { data: goldData, execute: fetchGold } = useApi(() => api.gold());
  const { data: signalData, execute: fetchSignal } = useApi(() => api.signal());
  useEffect(() => { fetchGold(); }, [fetchGold, refreshKey]);
  useEffect(() => { fetchSignal(); }, [fetchSignal, refreshKey]);

  const sig = signalData?.signal;
  const tone = sig ? signalTone(sig.signal) : undefined;

  return (
    <div className="flex flex-wrap items-center gap-4 px-5 py-3 rounded-xl bg-[var(--surface-strong)] border border-[var(--border)] mb-4">
      <div className="flex items-baseline gap-2">
        <span className="text-xs muted-copy">金价</span>
        <span className="metric-value text-[var(--accent)]">{goldData?.latest_price?.toFixed(2) ?? '--'}</span>
      </div>
      {sig && (
        <>
          <div className="w-px h-6 bg-[var(--border)]" />
          <div className="flex items-baseline gap-2">
            <span className="text-xs muted-copy">信号</span>
            <span className="font-medium" style={{ color: tone }}>{signalLabel(sig.signal)}</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-xs muted-copy">评分</span>
            <span className="text-sm">{sig.score}</span>
          </div>
        </>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [lastRefresh, setLastRefresh] = useState('--');
  const [autoInterval, setAutoInterval] = useState(60_000);
  const [section, setSection] = useState<SectionKey>('market');
  const [visible, setVisible] = useState<Record<string, boolean>>(loadVisible);
  const [showCustomize, setShowCustomize] = useState(false);
  const autoTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(() => {
    setRefreshKey(k => k + 1);
    setLastRefresh(new Date().toLocaleTimeString());
  }, []);

  // Auto-refresh timer
  useEffect(() => {
    if (autoInterval <= 0) return;
    const timer = setInterval(refresh, autoInterval);
    autoTimerRef.current = timer;
    return () => clearInterval(timer);
  }, [autoInterval, refresh]);

  // Pause auto-refresh when page is hidden
  useEffect(() => {
    const handleVisibility = () => {
      if (document.hidden && autoTimerRef.current) {
        clearInterval(autoTimerRef.current);
        autoTimerRef.current = null;
      } else if (!document.hidden && autoInterval > 0 && !autoTimerRef.current) {
        autoTimerRef.current = setInterval(refresh, autoInterval);
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, [autoInterval, refresh]);

  useWebSocket('dashboard', ['price', 'signal', 'news'], () => {
    refresh();
  });

  const toggleVisible = (key: string) => {
    setVisible(prev => {
      const next = { ...prev, [key]: !(prev[key] ?? true) };
      try { localStorage.setItem(VISIBLE_KEY, JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  };

  const isVis = (key: string) => visible[key] ?? true;

  return (
    <main className="min-h-screen">
      <div className="dashboard-shell">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <p className="eyebrow">数据面板</p>
            <p className="text-sm muted-copy mt-1">
              <Link href="/" className="inline-link">报告</Link>
              <span className="mx-2">/</span>
              数据面板
            </p>
          </div>
          <div className="flex items-center gap-3">
            {autoInterval > 0 && (
              <span className="flex items-center gap-1.5 text-xs muted-copy">
                <span className="inline-block w-2 h-2 rounded-full bg-[var(--accent)] animate-pulse" />
                自动 {autoInterval / 1000}s
              </span>
            )}
            <span className="text-xs muted-copy">最后刷新: {lastRefresh}</span>
            <select
              value={autoInterval}
              onChange={e => setAutoInterval(Number(e.target.value))}
              className="data-pill bg-transparent cursor-pointer text-xs"
            >
              {REFRESH_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <button
              onClick={() => setShowCustomize(!showCustomize)}
              className="data-pill cursor-pointer text-xs hover:border-[var(--accent)] transition-colors"
            >
              定制
            </button>
            <button
              onClick={refresh}
              className="data-pill cursor-pointer hover:border-[var(--accent)] transition-colors"
            >
              全部刷新
            </button>
          </div>
        </div>

        {/* Section tabs */}
        <div className="flex gap-1.5 mb-4 flex-wrap">
          {SECTIONS.map(s => (
            <button
              key={s.key}
              onClick={() => setSection(s.key)}
              className={`data-pill cursor-pointer transition-colors ${section === s.key ? 'border-[var(--accent)] text-[var(--accent)]' : ''}`}
            >
              {s.label}
            </button>
          ))}
        </div>

        {/* Customize panel */}
        {showCustomize && (
          <div className="flex flex-wrap gap-2 mb-4 p-3 rounded-xl border border-[var(--border)] bg-[var(--surface-strong)]">
            {['系统状态', '行情图', '交易信号', '价格预测', '宏观数据', '新闻情绪', '央行黄金储备', 'COT 持仓', 'ETF 流量', '地缘政治风险', 'FedWatch', '中国宏观', 'AISC', '财经日历', '辩论引擎', '回测'].map(label => {
              const key = label;
              return (
                <button
                  key={key}
                  onClick={() => toggleVisible(key)}
                  className={`data-pill cursor-pointer text-xs transition-colors ${isVis(key) ? 'border-[var(--accent)]' : 'opacity-40'}`}
                >
                  {isVis(key) ? '✓ ' : ''}{label}
                </button>
              );
            })}
          </div>
        )}

        {/* Top metrics bar */}
        <TopMetricsBar refreshKey={refreshKey} />

        {/* Cards grid */}
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {/* System status: always visible */}
          <div className="md:col-span-2 xl:col-span-3">
            <SystemStatusCard refreshKey={refreshKey} />
          </div>

          {/* ── 行情概览 ── */}
          {section === 'market' && (
            <>
              {isVis('行情图') && <PriceChartCard refreshKey={refreshKey} />}
              {(isVis('交易信号') || isVis('新闻情绪')) && (
                <div className="md:col-span-2 xl:col-span-3 flex gap-4">
                  <div className="flex-1 min-w-0">{isVis('交易信号') && <SignalGaugeCard refreshKey={refreshKey} />}</div>
                  <div className="flex-1 min-w-0">{isVis('新闻情绪') && <NewsCard refreshKey={refreshKey} />}</div>
                </div>
              )}
              {/* 技术指标已集成在行情图子图中（RSI/MACD/布林带） */}
              {isVis('价格预测') && (
                <div className="md:col-span-2 xl:col-span-3">
                  <PredictionChartCard refreshKey={refreshKey} />
                </div>
              )}
            </>
          )}

          {/* ── 宏观数据 ── */}
          {section === 'macro' && (
            <>
              {isVis('宏观数据') && <MacroCard refreshKey={refreshKey} />}
              {isVis('FedWatch') && <FedWatchCard refreshKey={refreshKey} />}
              {isVis('中国宏观') && <ChinaMacroCard refreshKey={refreshKey} />}
              {isVis('新闻情绪') && <NewsCard refreshKey={refreshKey} />}
            </>
          )}

          {/* ── 补充数据 ── */}
          {section === 'extra' && (
            <>
              {isVis('央行黄金储备') && <CentralBankCard refreshKey={refreshKey} />}
              {isVis('COT 持仓') && <CotCard refreshKey={refreshKey} />}
              {isVis('ETF 流量') && <EtfFlowCard refreshKey={refreshKey} />}
              {isVis('地缘政治风险') && <GeopolCard refreshKey={refreshKey} />}
              {isVis('AISC') && <AiscCard refreshKey={refreshKey} />}
              {isVis('财经日历') && <CalendarCard refreshKey={refreshKey} />}
            </>
          )}

          {/* ── 工具 ── */}
          {section === 'tools' && (
            <>
              {isVis('辩论引擎') && (
                <div className="md:col-span-2 xl:col-span-3">
                  <DebateCard />
                </div>
              )}
              {isVis('回测') && <BacktestCard refreshKey={refreshKey} />}
            </>
          )}
        </div>
      </div>
    </main>
  );
}
