'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { SectionCard, LoadingSkeleton, ErrorCard, DataTable, useApi } from '../shared';

export function sentimentLabel(label: string) {
  if (label === 'bullish') return '看多';
  if (label === 'bearish') return '看空';
  return '中性';
}

export function MacroCard({ refreshKey }: { refreshKey: number }) {
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

export function NewsCard({ refreshKey }: { refreshKey: number }) {
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
