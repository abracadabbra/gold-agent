'use client';

import { useEffect } from 'react';
import { api } from '@/lib/api';
import { useApi } from '../shared';
import { signalLabel, signalTone } from './signal-gauge';

export function TopMetricsBar({ refreshKey }: { refreshKey: number }) {
  const { data: goldData, execute: fetchGold } = useApi(() => api.gold());
  const { data: signalData, execute: fetchSignal } = useApi(() => api.signal());
  useEffect(() => { fetchGold(); }, [fetchGold, refreshKey]);
  useEffect(() => { fetchSignal(); }, [fetchSignal, refreshKey]);

  const sig = signalData?.unavailable ? null : signalData?.signal;
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
