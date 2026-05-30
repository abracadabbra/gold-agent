'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import type { BacktestResult } from '@/lib/types';
import { SectionCard, MetricBadge, TitleWithHelp, EXTRA_HELP, useApi } from '../shared';

export function BacktestCard({ refreshKey }: { refreshKey: number }) {
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
    <SectionCard title={<TitleWithHelp title="回测" help={EXTRA_HELP.backtest} />} delay={370}>
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
