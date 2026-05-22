'use client';

import { useState, useEffect, useCallback, useRef } from 'react';

/* ─── Shared UI Components ─── */

export function SectionCard({
  title, children, delay = 0, className = '',
}: {
  title: string | React.ReactNode;
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

export function LoadingSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      <div className="h-4 bg-[var(--border)] rounded w-3/4" />
      <div className="h-4 bg-[var(--border)] rounded w-1/2" />
      <div className="h-4 bg-[var(--border)] rounded w-5/6" />
    </div>
  );
}

export function ErrorCard({ title, error, delay, onRetry, className = '' }: {
  title: string;
  error: string;
  delay: number;
  onRetry: () => void;
  className?: string;
}) {
  return (
    <SectionCard title={title} delay={delay} className={className}>
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

export function MetricBadge({ label, value, color, children }: {
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

export function DataTable({ columns, rows }: { columns: string[]; rows: Record<string, unknown>[] }) {
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

export function CollapseSection({ label, defaultOpen = false, children }: {
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

export function useApi<T>(fetcher: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fetcherRef = useRef(fetcher);

  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  const execute = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setLoading(true);
    }
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

/* ─── Help Text ─── */

export const PREDICTION_HELP =
  '基于 Prophet 模型的时序预测: 蓝线为历史收盘价，金线为预测中值，金色阴影为 95% 置信区间。预测仅作为趋势参考，不构成投资建议。';

export const EXTRA_HELP: Record<string, string> = {
  central_bank: '各国央行官方黄金储备量（吨），数据来源 IMF IFS / WGC。排名靠前的国家包括美国(8133t)、德国(3352t)、IMF(2814t)等。',
  cot: 'CFTC 持仓报告: Managed Money(投机)多头/空头 vs Producer(套保)多头/空头，反映市场情绪和持仓结构。',
  etf_flow: '黄金 ETF 资金流量: 美元计价的每日流入/流出和总资产管理规模(AUM)。正流量代表资金流入。',
  geopol: '地缘政治风险指数(GPR): 基于报纸文章中地缘政治风险关键词频度统计。>200 表示高风险时期。',
  aisc: '全球黄金生产全维持成本(AISC): 包含采矿、加工、管理费用及维持资本。当前约 $1,270-1,385/oz。',
  calendar: '重要财经事件日历: 包括美联储利率决议、非农就业、CPI 等对金价有重大影响的数据发布。',
  fedwatch: 'CME FedWatch 工具: 基于联邦基金利率期货的 FOMC 会议加息/降息概率预测。',
  china_macro: '中国经济指标: CPI(通胀)、PPI(工业品价格)、PMI(制造业景气度)、M2(货币供应)、GDP(经济增长)、LPR(基准利率)、USD/CNY(汇率)。',
  backtest: '用历史数据模拟交易策略表现。当前策略 golden_cross(金叉): 短期均线(MA20)上穿长期均线(MA50)买入，下穿卖出。结果仅供参考，不构成投资建议。',
};

export function TitleWithHelp({ title, help }: { title: string; help?: string }) {
  if (!help) return <>{title}</>;
  return (
    <span className="flex items-center gap-1.5">
      {title}
      <span className="relative group">
        <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-[var(--muted)] text-[10px] cursor-help text-[var(--muted)] leading-none">?</span>
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 rounded-lg text-xs whitespace-nowrap bg-[var(--foreground)] text-[var(--background)] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-lg">{help}</span>
      </span>
    </span>
  );
}
