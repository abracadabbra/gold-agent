'use client';

import { useEffect } from 'react';
import {
  Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, AreaChart, Area,
} from 'recharts';
import { api } from '@/lib/api';
import { SectionCard, LoadingSkeleton, ErrorCard, PREDICTION_HELP, useApi } from './shared';

export default function PredictionChartCard({ refreshKey }: { refreshKey: number }) {
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
