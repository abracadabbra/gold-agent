'use client';

import { useEffect } from 'react';
import { api } from '@/lib/api';
import { SectionCard, LoadingSkeleton, ErrorCard, MetricBadge, useApi } from '../shared';

export function SystemStatusCard({ refreshKey }: { refreshKey: number }) {
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
