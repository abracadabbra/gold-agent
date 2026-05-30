'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useWebSocket } from '@/lib/api';
import { SectionCard, LoadingSkeleton } from './shared';
import { SystemStatusCard } from './components/system-status';
import { PriceChartCard } from './components/price-chart';
import { SignalGaugeCard } from './components/signal-gauge';
import { MacroCard, NewsCard } from './components/macro-news';
import { DebateCard } from './components/debate';
import { BacktestCard } from './components/backtest';
import { CentralBankCard, CotCard, EtfFlowCard, GeopolCard, FedWatchCard, ChinaMacroCard, AiscCard } from './components/extra-data';
import { CalendarCard } from './components/calendar';
import { TopMetricsBar } from './components/top-metrics';

const PredictionChartCard = dynamic(() => import('./prediction-chart'), {
  ssr: false,
  loading: () => <SectionCard title="价格预测" delay={210}><LoadingSkeleton /></SectionCard>,
});

/* ─── Page constants ─── */

const REFRESH_OPTIONS = [
  { label: '关闭', value: 0 },
  { label: '30s', value: 30_000 },
  { label: '60s', value: 60_000 },
  { label: '120s', value: 120_000 },
];

const SECTIONS = [
  { key: 'market', label: '行情概览' },
  { key: 'macro', label: '宏观数据' },
  { key: 'extra', label: '补充数据' },
  { key: 'tools', label: '工具' },
] as const;

type SectionKey = typeof SECTIONS[number]['key'];

const VISIBLE_KEY = 'dash_visible_cards';

function loadVisible(): Record<string, boolean> {
  if (typeof window === 'undefined') return {};
  try {
    return JSON.parse(localStorage.getItem(VISIBLE_KEY) || '{}');
  } catch { return {}; }
}

/* ─── Dashboard Page ─── */

export default function DashboardPage() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [lastRefresh, setLastRefresh] = useState('--');
  const [autoInterval, setAutoInterval] = useState(60_000);
  const [section, setSection] = useState<SectionKey>('market');
  const [visible, setVisible] = useState<Record<string, boolean>>(loadVisible);
  const [showCustomize, setShowCustomize] = useState(false);
  const autoTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(() => {
    setRefreshKey(k => k + 1);
    setLastRefresh(new Date().toLocaleTimeString());
  }, []);

  // Auto-refresh timer
  useEffect(() => {
    if (autoInterval <= 0) return;
    const timer = setInterval(refresh, autoInterval);
    autoTimerRef.current = timer;
    return () => clearInterval(timer);
  }, [autoInterval, refresh]);

  // Pause auto-refresh when page is hidden
  useEffect(() => {
    const handleVisibility = () => {
      if (document.hidden && autoTimerRef.current) {
        clearInterval(autoTimerRef.current);
        autoTimerRef.current = null;
      } else if (!document.hidden && autoInterval > 0 && !autoTimerRef.current) {
        autoTimerRef.current = setInterval(refresh, autoInterval);
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, [autoInterval, refresh]);

  const [fastRefreshKey, setFastRefreshKey] = useState(0);
  const [newsRefreshKey, setNewsRefreshKey] = useState(0);

  useWebSocket('dashboard', ['price', 'signal', 'news'], (channel: string) => {
    if (channel === 'price' || channel === 'signal') {
      setFastRefreshKey(k => k + 1);
    } else if (channel === 'news') {
      setNewsRefreshKey(k => k + 1);
    }
  });

  const toggleVisible = (key: string) => {
    setVisible(prev => {
      const next = { ...prev, [key]: !(prev[key] ?? true) };
      try { localStorage.setItem(VISIBLE_KEY, JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  };

  const isVis = (key: string) => visible[key] ?? true;

  return (
    <main className="min-h-screen">
      <div className="dashboard-shell">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <p className="eyebrow">数据面板</p>
            <p className="text-sm muted-copy mt-1">
              <Link href="/" className="inline-link">报告</Link>
              <span className="mx-2">/</span>
              数据面板
            </p>
          </div>
          <div className="flex items-center gap-3">
            {autoInterval > 0 && (
              <span className="flex items-center gap-1.5 text-xs muted-copy">
                <span className="inline-block w-2 h-2 rounded-full bg-[var(--accent)] animate-pulse" />
                自动 {autoInterval / 1000}s
              </span>
            )}
            <span className="text-xs muted-copy">最后刷新: {lastRefresh}</span>
            <select
              value={autoInterval}
              onChange={e => setAutoInterval(Number(e.target.value))}
              className="data-pill bg-transparent cursor-pointer text-xs"
            >
              {REFRESH_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <button
              onClick={() => setShowCustomize(!showCustomize)}
              className="data-pill cursor-pointer text-xs hover:border-[var(--accent)] transition-colors"
            >
              定制
            </button>
            <button
              onClick={refresh}
              className="data-pill cursor-pointer hover:border-[var(--accent)] transition-colors"
            >
              全部刷新
            </button>
          </div>
        </div>

        {/* Section tabs */}
        <div className="flex gap-1.5 mb-4 flex-wrap">
          {SECTIONS.map(s => (
            <button
              key={s.key}
              onClick={() => setSection(s.key)}
              className={`data-pill cursor-pointer transition-colors ${section === s.key ? 'border-[var(--accent)] text-[var(--accent)]' : ''}`}
            >
              {s.label}
            </button>
          ))}
        </div>

        {/* Customize panel */}
        {showCustomize && (
          <div className="flex flex-wrap gap-2 mb-4 p-3 rounded-xl border border-[var(--border)] bg-[var(--surface-strong)]">
            {['系统状态', '行情图', '交易信号', '价格预测', '宏观数据', '新闻情绪', '央行黄金储备', 'COT 持仓', 'ETF 流量', '地缘政治风险', 'FedWatch', '中国宏观', 'AISC', '财经日历', '辩论引擎', '回测'].map(label => {
              const key = label;
              return (
                <button
                  key={key}
                  onClick={() => toggleVisible(key)}
                  className={`data-pill cursor-pointer text-xs transition-colors ${isVis(key) ? 'border-[var(--accent)]' : 'opacity-40'}`}
                >
                  {isVis(key) ? '✓ ' : ''}{label}
                </button>
              );
            })}
          </div>
        )}

        {/* Top metrics bar */}
        <TopMetricsBar refreshKey={refreshKey} />

        {/* Cards grid */}
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {/* System status: always visible */}
          <div className="md:col-span-2 xl:col-span-3">
            <SystemStatusCard refreshKey={refreshKey} />
          </div>

          {/* ── 行情概览 ── */}
          {section === 'market' && (
            <>
              {isVis('行情图') && <PriceChartCard refreshKey={fastRefreshKey} />}
              {(isVis('交易信号') || isVis('新闻情绪')) && (
                <div className="md:col-span-2 xl:col-span-3 flex gap-4 items-stretch">
                  <div className="flex-1 min-w-0 flex flex-col">{isVis('交易信号') && <SignalGaugeCard refreshKey={fastRefreshKey} />}</div>
                  <div className="flex-1 min-w-0 flex flex-col">{isVis('新闻情绪') && <NewsCard refreshKey={newsRefreshKey} />}</div>
                </div>
              )}
              {isVis('价格预测') && (
                <div className="md:col-span-2 xl:col-span-3">
                  <PredictionChartCard refreshKey={fastRefreshKey} />
                </div>
              )}
            </>
          )}

          {/* ── 宏观数据 ── */}
          {section === 'macro' && (
            <>
              {isVis('宏观数据') && <MacroCard refreshKey={refreshKey} />}
              {isVis('FedWatch') && <FedWatchCard refreshKey={refreshKey} />}
              {isVis('中国宏观') && <ChinaMacroCard refreshKey={refreshKey} />}
            </>
          )}

          {/* ── 补充数据 ── */}
          {section === 'extra' && (
            <>
              {isVis('央行黄金储备') && <CentralBankCard refreshKey={refreshKey} />}
              {isVis('COT 持仓') && <CotCard refreshKey={refreshKey} />}
              {isVis('ETF 流量') && <EtfFlowCard refreshKey={refreshKey} />}
              {isVis('地缘政治风险') && <GeopolCard refreshKey={refreshKey} />}
              {isVis('AISC') && <AiscCard refreshKey={refreshKey} />}
              {isVis('财经日历') && <CalendarCard refreshKey={refreshKey} />}
            </>
          )}

          {/* ── 工具 ── */}
          {section === 'tools' && (
            <>
              {isVis('辩论引擎') && (
                <div className="md:col-span-2 xl:col-span-3">
                  <DebateCard />
                </div>
              )}
              {isVis('回测') && (
                <div className="md:col-span-2 xl:col-span-3">
                  <BacktestCard refreshKey={refreshKey} />
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </main>
  );
}
