'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import type { DebateResponse } from '@/lib/types';
import { SectionCard, CollapseSection, TitleWithHelp } from '../shared';

export function DebateCard() {
  const [data, setData] = useState<DebateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stageResults, setStageResults] = useState<Record<string, { label: string; color: string; result: unknown }>>({});
  const [stageOrder] = useState(['bull', 'bear', 'audit', 'verdict']);
  const esRef = useRef<EventSource | null>(null);

  const run = useCallback(() => {
    setLoading(true);
    setError(null);
    setData(null);
    setStageResults({});

    // Close previous connection
    if (esRef.current) {
      esRef.current.close();
    }

    const es = new EventSource(`${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8001'}/api/debate/run/stream`);
    esRef.current = es;

    es.addEventListener('stage', (e: MessageEvent) => {
      const payload = JSON.parse(e.data);
      setStageResults(prev => ({
        ...prev,
        [payload.stage]: { label: payload.label, color: payload.color, result: payload.result },
      }));
    });

    es.addEventListener('complete', (e: MessageEvent) => {
      const payload = JSON.parse(e.data);
      setData({ summary: payload.summary, detail: payload.detail });
      es.close();
      esRef.current = null;
      setLoading(false);
    });

    es.addEventListener('error', (e: MessageEvent) => {
      let msg = '辩论异常';
      try { msg = JSON.parse(e.data).error; } catch { /* ignore */ }
      setError(msg);
      es.close();
      esRef.current = null;
      setLoading(false);
    });
  }, []);

  // Cleanup on unmount
  useEffect(() => () => { esRef.current?.close(); }, []);

  const stageCompleted = (stage: string) => stage in stageResults || (data != null);

  return (
    <SectionCard title={<TitleWithHelp title="辩论引擎" help="4 个 AI 角色(看多/看空/数据审计/最终裁决)就黄金市场进行多轮辩论。每个阶段独立调用 LLM，结果实时展示。" />} delay={330}>
      <div className="flex items-center gap-3 mb-3">
        <button
          onClick={run}
          disabled={loading}
          className="data-pill cursor-pointer hover:border-[var(--accent)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? '辩论进行中...' : '运行辩论'}
        </button>
      </div>

      {/* 阶段进度条 */}
      {loading && (
        <div className="flex flex-wrap gap-2 mb-4">
          {stageOrder.map((s, i) => {
            const done = s in stageResults;
            const current = !done && (i === 0 || stageOrder.slice(0, i).every(stageCompleted));
            return (
              <span
                key={s}
                className="data-pill text-xs flex items-center gap-1"
                style={{
                  borderColor: done ? stageResults[s].color : current ? 'var(--accent)' : 'var(--border)',
                  opacity: done || current ? 1 : 0.4,
                }}
              >
                {done ? '✓' : current ? (
                  <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                ) : '⏳'}
                {' '}{{ bull: '看多方', bear: '看空方', audit: '数据审计', verdict: '最终裁决' }[s]}
              </span>
            );
          })}
        </div>
      )}

      {error && <p className="text-[var(--danger)] mb-3">{error}</p>}

      {/* 阶段性结果实时展示 */}
      {stageOrder.map(s => {
        const sr = stageResults[s];
        if (!sr) return null;
        return (
          <CollapseSection key={s} label={<span style={{ color: sr.color }}>{sr.label}</span>}>
            <pre className="text-xs whitespace-pre-wrap leading-6">{JSON.stringify(sr.result, null, 2)}</pre>
          </CollapseSection>
        );
      })}

      {/* 完整结果 */}
      {data && (
        <div className="space-y-2 mt-3 border-t border-[var(--border)] pt-3">
          {data.summary && (
            <pre className="text-xs whitespace-pre-wrap text-[var(--muted)] leading-6 mb-3 p-3 rounded-xl bg-[rgba(255,253,247,0.4)] border border-[var(--border)]">
              {data.summary}
            </pre>
          )}
          {stageOrder.map(s => {
            const roleData = data.detail[s as keyof typeof data.detail];
            if (!roleData) return null;
            return null; // already shown above as stageResults
          })}
        </div>
      )}
    </SectionCard>
  );
}
