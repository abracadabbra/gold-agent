'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { SectionCard, LoadingSkeleton, ErrorCard, MetricBadge, DataTable, TitleWithHelp, EXTRA_HELP, useApi } from '../shared';

export function CentralBankCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.extraData());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="央行黄金储备" delay={410}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="央行黄金储备" error={error || '无数据'} delay={410} onRetry={execute} />;

  const cb = data.central_bank;
  const rows = cb.data as unknown as Record<string, unknown>[];
  const columns = ['country', 'date', 'gold_reserves_tonnes', 'rank'];

  return (
    <SectionCard title={<TitleWithHelp title="央行黄金储备" help={EXTRA_HELP.central_bank} />} delay={410}>
      <div className="flex flex-wrap gap-2 mb-3">
        <span className="data-pill">国家: {new Set(rows.map(r => r.country as string)).size}</span>
        <span className="data-pill">记录: {cb.records}</span>
        {cb._status === 'error' && <span className="data-pill text-[var(--danger)]">部分失败</span>}
      </div>
      <DataTable columns={columns} rows={rows.slice(0, 15)} />
    </SectionCard>
  );
}

export function CotCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.extraData());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="COT 持仓" delay={450}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="COT 持仓" error={error || '无数据'} delay={450} onRetry={execute} />;

  const cot = data.cot;
  const rows = cot.data as unknown as Record<string, unknown>[];
  const columns = ['date', 'exchange', 'open_interest', 'managed_money_long', 'managed_money_short', 'producer_long', 'producer_short'];

  return (
    <SectionCard title={<TitleWithHelp title="COT 持仓" help={EXTRA_HELP.cot} />} delay={450}>
      <div className="flex flex-wrap gap-2 mb-3">
        <span className="data-pill">记录: {cot.records}</span>
        {cot._status === 'error' && <span className="data-pill text-[var(--danger)]">失败</span>}
      </div>
      <DataTable columns={columns} rows={rows.slice(0, 10)} />
    </SectionCard>
  );
}

export function EtfFlowCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.extraData());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="ETF 流量" delay={490}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="ETF 流量" error={error || '无数据'} delay={490} onRetry={execute} />;

  const etf = data.etf_flow;
  const rows = etf.data as unknown as Record<string, unknown>[];
  const columns = ['date', 'fund_name', 'region', 'flow_usd', 'aum_usd'];

  return (
    <SectionCard title={<TitleWithHelp title="ETF 流量" help={EXTRA_HELP.etf_flow} />} delay={490}>
      <div className="flex flex-wrap gap-2 mb-3">
        <span className="data-pill">记录: {etf.records}</span>
        {etf._status === 'error' && <span className="data-pill text-[var(--danger)]">失败</span>}
      </div>
      <DataTable columns={columns} rows={rows.slice(0, 10)} />
    </SectionCard>
  );
}

export function GeopolCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.extraData());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="地缘政治风险" delay={530}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="地缘政治风险" error={error || '无数据'} delay={530} onRetry={execute} />;

  const gp = data.geopol;
  const rows = gp.data as unknown as Record<string, unknown>[];
  const columns = ['date', 'gpr_index', 'gpr_threats', 'gpr_acts'].filter(c => rows.some(r => r[c] != null));

  return (
    <SectionCard title={<TitleWithHelp title="地缘政治风险" help={EXTRA_HELP.geopol} />} delay={530}>
      <div className="flex flex-wrap gap-2 mb-3">
        <span className="data-pill">记录: {gp.records}</span>
        {gp._status === 'error' && <span className="data-pill text-[var(--danger)]">失败</span>}
      </div>
      <DataTable columns={columns} rows={rows.slice(0, 10)} />
    </SectionCard>
  );
}

export function FedWatchCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.extraData());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="FedWatch 利率预期" delay={570}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="FedWatch 利率预期" error={error || '无数据'} delay={570} onRetry={execute} />;

  const fw = data.fedwatch;
  const rows = fw.data as unknown as Record<string, unknown>[];
  const latest = rows[0];

  return (
    <SectionCard title={<TitleWithHelp title="FedWatch 利率预期" help={EXTRA_HELP.fedwatch} />} delay={570}>
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

export function ChinaMacroCard({ refreshKey }: { refreshKey: number }) {
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
    <SectionCard title={<TitleWithHelp title="中国宏观数据" help={EXTRA_HELP.china_macro} />} delay={610}>
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

export function AiscCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi(() => api.extraData());
  useEffect(() => { execute(); }, [execute, refreshKey]);

  if (loading) return <SectionCard title="生产成本 AISC" delay={650}><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="生产成本 AISC" error={error || '无数据'} delay={650} onRetry={execute} />;

  const aisc = data.aisc;
  const rows = aisc.data as unknown as Record<string, unknown>[];
  const latest = rows[rows.length - 1];

  return (
    <SectionCard title={<TitleWithHelp title="生产成本 AISC" help={EXTRA_HELP.aisc} />} delay={650}>
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
