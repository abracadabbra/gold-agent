'use client';

import { useEffect } from 'react';
import { api } from '@/lib/api';
import { SectionCard, LoadingSkeleton, ErrorCard, DataTable, TitleWithHelp, EXTRA_HELP, useApi } from '../shared';

export function CalendarCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.calendar());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="财经日历" delay={680}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="财经日历" error={error || '无数据'} delay={680} onRetry={execute} />;

  const nextEvent = data.next_event;

  return (
    <SectionCard title={<TitleWithHelp title="财经日历" help={EXTRA_HELP.calendar} />} delay={680} className="xl:col-span-1">
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
