'use client';

import { useEffect } from 'react';
import { api } from '@/lib/api';
import { SectionCard, LoadingSkeleton, ErrorCard, MetricBadge, useApi } from '../shared';

export function signalLabel(s: string) {
  const map: Record<string, string> = { strong_buy: '强烈买入', buy: '买入', neutral: '中性', sell: '卖出', strong_sell: '强烈卖出' };
  return map[s] || s;
}

export function signalTone(s: string) {
  if (s === 'strong_buy' || s === 'buy') return 'var(--accent)';
  if (s === 'strong_sell' || s === 'sell') return 'var(--danger)';
  return 'var(--muted)';
}

export function SignalGaugeCard({ refreshKey }: { refreshKey: number }) {
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

export function RsiGauge({ ind }: { ind: Record<string, number> }) {
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

export function MacdGauge({ ind }: { ind: Record<string, number> }) {
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

export function BbGauge({ ind, price }: { ind: Record<string, number>; price: number }) {
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
