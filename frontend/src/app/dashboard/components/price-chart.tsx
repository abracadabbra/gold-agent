'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { api } from '@/lib/api';
import type { GoldPriceResponse, IndicatorsResponse, OhlcvPoint } from '@/lib/types';
import { createChart, ColorType, CrosshairMode, CandlestickSeries, LineSeries, HistogramSeries } from 'lightweight-charts';
import { SectionCard, LoadingSkeleton, ErrorCard } from '../shared';
import { RsiGauge, MacdGauge, BbGauge } from './signal-gauge';

const SUB_TAB_HELP: Record<string, string> = {
  spread: '国际金价(蓝)与沪金(橙)走势对比，观察国内外价差',
  rsi: '相对强弱指标(RSI): >70 超买(可能回调), <30 超卖(可能反弹)',
  macd: '指数平滑异同平均线: 快线上穿信号线为买入信号，下穿为卖出信号',
  bb: '布林带: 价格触及上轨可能超买，触及下轨可能超卖; 带宽收窄预示变盘',
};

export function PriceChartCard({ refreshKey }: { refreshKey: number }) {
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
          {data.source !== source && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--accent)]/10 text-[var(--accent)]">
              实际数据源: {data.source === 'shfe' ? '沪金' : data.source}
            </span>
          )}
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
