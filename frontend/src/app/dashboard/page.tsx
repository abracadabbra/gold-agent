'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import type { DebateResponse, BacktestResult } from '@/lib/types';

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

function GoldPriceCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.gold());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="行情数据" delay={90}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="行情数据" error={error || '无数据'} delay={90} onRetry={execute} />;

  const recent = data.data.slice(-10);

  return (
    <SectionCard title="行情数据" delay={90}>
      {data.latest_price != null && (
        <p className="metric-value text-[var(--accent)] mb-2">{data.latest_price.toFixed(2)}</p>
      )}
      <div className="flex flex-wrap gap-2 mb-3">
        <span className="data-pill">源: {data.source}</span>
        <span className="data-pill">记录: {data.records}</span>
      </div>
      <DataTable
        columns={['date', 'open', 'high', 'low', 'close', 'volume']}
        rows={recent as unknown as Record<string, unknown>[]}
      />
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

function SignalCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.signal());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="交易信号" delay={130}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="交易信号" error={error || '无数据'} delay={130} onRetry={execute} />;

  const sig = data.signal;
  const tone = signalTone(sig.signal);
  const pct = ((sig.score + 100) / 2).toFixed(0);

  return (
    <SectionCard title="交易信号" delay={130}>
      <p className="text-2xl font-display mb-2" style={{ color: tone }}>{signalLabel(sig.signal)}</p>

      <div className="space-y-1">
        <MetricBadge label="评分" value={`${sig.score} / 100`} />
        <MetricBadge label="置信度" value={`${(sig.confidence * 100).toFixed(0)}%`} />
        {sig.stop_loss && <MetricBadge label="止损" value={sig.stop_loss.toFixed(2)} />}
        {sig.take_profit && <MetricBadge label="止盈" value={sig.take_profit.toFixed(2)} />}
      </div>

      <div className="mt-3 h-2 rounded-full bg-gray-200 relative overflow-hidden">
        <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-gray-400 z-10" />
        <div
          className="absolute top-0 bottom-0 rounded-full transition-all duration-500"
          style={{
            left: `${sig.score >= 0 ? 50 : 50 + sig.score / 2}%`,
            width: `${Math.abs(sig.score)}%`,
            backgroundColor: tone,
          }}
        />
      </div>
      <p className="text-xs text-right muted-copy mt-1">{pct}%</p>

      {sig.reasons?.length > 0 && (
        <ul className="report-list mt-3 space-y-0.5 text-sm">
          {sig.reasons.map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      )}
    </SectionCard>
  );
}

const indicatorGroups = [
  { label: '移动平均线', keys: ['ma5', 'ma10', 'ma20', 'ma60', 'ema12', 'ema26'] },
  { label: 'MACD', keys: ['macd_line', 'macd_signal', 'macd_histogram'] },
  { label: 'RSI / 随机指标', keys: ['rsi14', 'stoch_k', 'stoch_d'] },
  { label: '布林带', keys: ['bb_upper', 'bb_middle', 'bb_lower'] },
  { label: 'ATR', keys: ['atr14'] },
  { label: 'ADX', keys: ['adx'] },
  { label: 'Supertrend', keys: ['supertrend', 'supertrend_direction'] },
  { label: 'OBV', keys: ['obv'] },
];

function IndicatorsCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.indicators());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="技术指标" delay={170}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="技术指标" error={error || '无数据'} delay={170} onRetry={execute} />;

  const ind = data.indicators;

  return (
    <SectionCard title="技术指标" delay={170}>
      <p className="metric-value text-[var(--accent)] mb-3">{data.price.toFixed(2)}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        {indicatorGroups.map(group => {
          const items = group.keys.filter(k => ind[k] != null);
          if (!items.length) return null;
          return (
            <div key={group.label} className="p-3 rounded-xl border border-[var(--border)] bg-[rgba(255,253,247,0.4)]">
              <p className="text-xs font-semibold muted-copy uppercase tracking-wider mb-1.5">{group.label}</p>
              <div className="space-y-0.5">
                {items.map(k => (
                  <div key={k} className="flex justify-between text-sm">
                    <span className="muted-copy">{k}</span>
                    <span className="font-medium">{typeof ind[k] === 'number' ? ind[k].toFixed(4) : String(ind[k])}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </SectionCard>
  );
}

function PredictionCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.prediction());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="价格预测" delay={210}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="价格预测" error={error || '无数据'} delay={210} onRetry={execute} />;

  return (
    <SectionCard title="价格预测" delay={210}>
      <div className="flex items-center gap-3 mb-3">
        <span className="data-pill">趋势: {data.trend === 'up' ? '↑ 上涨' : data.trend === 'down' ? '↓ 下跌' : '→ 震荡'}</span>
        <span className="data-pill">预测项: {data.prediction.length}</span>
      </div>
      <DataTable
        columns={['ds', 'yhat', 'yhat_lower', 'yhat_upper']}
        rows={data.prediction as unknown as Record<string, unknown>[]}
      />
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

/* ─── Page ─── */

export default function DashboardPage() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [lastRefresh, setLastRefresh] = useState('--');

  const refresh = () => {
    setRefreshKey(k => k + 1);
    setLastRefresh(new Date().toLocaleTimeString());
  };

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

          <GoldPriceCard refreshKey={refreshKey} />
          <SignalCard refreshKey={refreshKey} />
          <NewsCard refreshKey={refreshKey} />

          <div className="md:col-span-2">
            <IndicatorsCard refreshKey={refreshKey} />
          </div>
          <MacroCard refreshKey={refreshKey} />

          <div className="md:col-span-2">
            <PredictionCard refreshKey={refreshKey} />
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
        </div>
      </div>
    </main>
  );
}
