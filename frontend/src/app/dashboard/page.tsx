'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import { api, useWebSocket } from '@/lib/api';
import type { DebateResponse, BacktestResult, CalendarResponse } from '@/lib/types';
import {
  ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, AreaChart, Area,
} from 'recharts';

/* ─── Shared UI ─── */

function SectionCard({
  title, children, delay = 0, className = '',
}: {
  title: string;
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

function ErrorCard({ title, error, delay, onRetry }: {
  title: string;
  error: string;
  delay: number;
  onRetry: () => void;
}) {
  return (
    <SectionCard title={title} delay={delay}>
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

  const execute = useCallback(async () => {
    setLoading(true);
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

function ChartTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ payload: Record<string, unknown> }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  const fmt = (v: unknown) => v != null ? Number(v).toFixed(2) : '-';
  const vol = (v: unknown) => v != null ? Number(v).toLocaleString() : '-';
  return (
    <div className="bg-[var(--surface-strong)] border border-[var(--border)] rounded-lg p-3 text-sm shadow-lg">
      <p className="muted-copy mb-1">{label}</p>
      <div className="space-y-0.5">
        <p>开: {fmt(d?.open)}</p>
        <p>高: {fmt(d?.high)}</p>
        <p>低: {fmt(d?.low)}</p>
        <p>收: <span style={{ color: '#d4a849' }}>{fmt(d?.close)}</span></p>
        <p>量: {vol(d?.volume)}</p>
      </div>
    </div>
  );
}

function PriceChartCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.gold());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="行情数据" delay={90}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="行情数据" error={error || '无数据'} delay={90} onRetry={execute} />;

  const chartData = data.data.slice(-100);
  if (!chartData.length) return <SectionCard title="行情数据" delay={90}><p className="muted-copy">无数据</p></SectionCard>;

  return (
    <SectionCard title="行情数据" delay={90}>
      {data.latest_price != null && (
        <p className="metric-value text-[var(--accent)] mb-2">{data.latest_price.toFixed(2)}</p>
      )}
      <div className="flex flex-wrap gap-2 mb-3">
        <span className="data-pill">源: {data.source}</span>
        <span className="data-pill">记录: {data.records}</span>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="var(--muted)" tickFormatter={(v: string) => v.slice(0, 10)} />
          <YAxis yAxisId="price" stroke="var(--muted)" tick={{ fontSize: 12 }} />
          <YAxis yAxisId="volume" orientation="right" hide />
          <Tooltip content={<ChartTooltip />} />
          <Bar yAxisId="volume" dataKey="volume" fill="rgba(128,128,128,0.3)" barSize={4} />
          <Line yAxisId="price" type="monotone" dataKey="close" stroke="#d4a849" dot={false} strokeWidth={2} />
        </ComposedChart>
      </ResponsiveContainer>
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

  if (loading) return <SectionCard title="交易信号" delay={130}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="交易信号" error={error || '无数据'} delay={130} onRetry={execute} />;

  const sig = data.signal;
  const tone = signalTone(sig.signal);
  const pct = Math.min(100, Math.max(0, ((sig.score + 100) / 200) * 100));

  return (
    <SectionCard title="交易信号" delay={130}>
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
  const middle = ind.bb_middle;
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

function IndicatorGaugeCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.indicators());
  useEffect(() => { execute(); }, [execute, refreshKey]);
  const [tab, setTab] = useState('rsi');

  if (loading) return <SectionCard title="技术指标" delay={170}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="技术指标" error={error || '无数据'} delay={170} onRetry={execute} />;

  const ind = data.indicators;

  return (
    <SectionCard title="技术指标" delay={170}>
      <p className="metric-value text-[var(--accent)] mb-2">{data.price.toFixed(2)}</p>

      <div className="flex gap-2 mb-3">
        {['rsi', 'macd', 'bb'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`data-pill cursor-pointer transition-colors ${tab === t ? 'border-[var(--accent)] text-[var(--accent)]' : ''}`}
          >
            {t === 'rsi' ? 'RSI' : t === 'macd' ? 'MACD' : '布林带'}
          </button>
        ))}
      </div>

      {tab === 'rsi' && <RsiGauge ind={ind} />}
      {tab === 'macd' && <MacdGauge ind={ind} />}
      {tab === 'bb' && <BbGauge ind={ind} price={data.price} />}

      {data.summary && (
        <details className="mt-3">
          <summary className="text-sm cursor-pointer muted-copy hover:text-[var(--accent)]">查看详情</summary>
          <pre className="mt-2 text-xs whitespace-pre-wrap text-[var(--muted)] leading-6">{data.summary}</pre>
        </details>
      )}
    </SectionCard>
  );
}

function PredictionChartCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.prediction());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="价格预测" delay={210}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="价格预测" error={error || '无数据'} delay={210} onRetry={execute} />;

  const chartData = data.prediction;
  if (!chartData.length) return <SectionCard title="价格预测" delay={210}><p className="muted-copy">无数据</p></SectionCard>;

  return (
    <SectionCard title="价格预测" delay={210}>
      <div className="flex items-center gap-3 mb-3">
        <span className="data-pill">趋势: {data.trend === 'up' ? '↑ 上涨' : data.trend === 'down' ? '↓ 下跌' : '→ 震荡'}</span>
        <span className="data-pill">预测项: {data.prediction.length}</span>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id="bandGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#d4a849" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#d4a849" stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="ds" tick={{ fontSize: 12 }} stroke="var(--muted)" />
          <YAxis stroke="var(--muted)" tick={{ fontSize: 12 }} />
          <Tooltip
            contentStyle={{ background: 'var(--surface-strong)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 13 }}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            formatter={(value: any, name: any) => {
              const labels: Record<string, string> = { yhat: '预测值', yhat_lower: '下限', yhat_upper: '上限' };
              return [Number(value).toFixed(2), labels[name] || name];
            }}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            labelFormatter={(label: any) => `日期: ${label}`}
          />
          <Area type="monotone" dataKey="yhat_upper" fill="url(#bandGrad)" stroke="none" />
          <Area type="monotone" dataKey="yhat_lower" fill="var(--surface-strong)" stroke="none" />
          <Line type="monotone" dataKey="yhat" stroke="#d4a849" strokeWidth={2} dot={false} />
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
              <span className="flex-1">{item.title}</span>
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

export default function DashboardPage() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [lastRefresh, setLastRefresh] = useState('--');

  const refresh = () => {
    setRefreshKey(k => k + 1);
    setLastRefresh(new Date().toLocaleTimeString());
  };

  useWebSocket('dashboard', ['price', 'signal', 'news'], (channel) => {
    refresh();
  });

  return (
    <main className="min-h-screen">
      <div className="dashboard-shell">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
          <div>
            <p className="eyebrow">数据面板</p>
            <p className="text-sm muted-copy mt-1">
              <Link href="/" className="inline-link">报告</Link>
              <span className="mx-2">/</span>
              数据面板
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs muted-copy">最后刷新: {lastRefresh}</span>
            <button
              onClick={refresh}
              className="data-pill cursor-pointer hover:border-[var(--accent)] transition-colors"
            >
              全部刷新
            </button>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <div className="md:col-span-2 xl:col-span-3">
            <SystemStatusCard refreshKey={refreshKey} />
          </div>

          <PriceChartCard refreshKey={refreshKey} />
          <SignalGaugeCard refreshKey={refreshKey} />
          <NewsCard refreshKey={refreshKey} />

          <div className="md:col-span-2">
            <IndicatorGaugeCard refreshKey={refreshKey} />
          </div>
          <MacroCard refreshKey={refreshKey} />

          <div className="md:col-span-2">
            <PredictionChartCard refreshKey={refreshKey} />
          </div>
          <BacktestCard refreshKey={refreshKey} />

          <div className="md:col-span-2 xl:col-span-3">
            <DebateCard />
          </div>

          {/* ── 补充数据卡片 ── */}
          <div className="md:col-span-2 xl:col-span-3">
            <h3 className="section-title !text-sm mb-2">补充数据</h3>
          </div>

          <CentralBankCard refreshKey={refreshKey} />
          <CotCard refreshKey={refreshKey} />
          <EtfFlowCard refreshKey={refreshKey} />
          <GeopolCard refreshKey={refreshKey} />
          <FedWatchCard refreshKey={refreshKey} />
          <ChinaMacroCard refreshKey={refreshKey} />
          <AiscCard refreshKey={refreshKey} />
          <CalendarCard refreshKey={refreshKey} />
        </div>
      </div>
    </main>
  );
}
