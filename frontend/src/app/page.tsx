'use client';
import { useState, useEffect } from 'react';
import Link from "next/link";
import { api } from '@/lib/api';

type MetricCardProps = {
  label: string;
  value: string;
  tone?: "accent" | "danger" | "default";
};

type SectionCardProps = {
  title: string;
  children: React.ReactNode;
  delay?: number;
  className?: string;
};

const labelMap: Record<string, string> = {
  strong_buy: '强烈看多', buy: '看多',
  neutral: '中性', sell: '看空', strong_sell: '强烈看空',
};

function MetricCard({ label, value, tone = "default" }: MetricCardProps) {
  const toneClass =
    tone === "danger"
      ? "text-[var(--danger)]"
      : tone === "accent"
        ? "text-[var(--accent)]"
        : "text-[var(--foreground)]";

  return (
    <div className="metric-card p-5 md:p-6">
      <p className="text-sm muted-copy">{label}</p>
      <p className={`metric-value mt-4 whitespace-pre-line ${toneClass}`}>{value}</p>
    </div>
  );
}

function SectionCard({ title, children, delay = 0, className = "" }: SectionCardProps) {
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

function toFixed(v: number | null | undefined, d = 2): string {
  if (v == null || isNaN(v)) return '-';
  return v.toFixed(d);
}

function latestPair<T>(data: T[], field: keyof T): [number | null, number | null] {
  const vals: number[] = [];
  for (let i = data.length - 1; i >= 0 && vals.length < 2; i--) {
    const v = data[i][field];
    if (v != null) vals.unshift(Number(v));
  }
  return vals.length >= 2 ? [vals[vals.length - 2], vals[vals.length - 1]] : [vals[vals.length - 1] ?? null, null];
}

function surpriseLabel(delta: number): string {
  const a = Math.abs(delta);
  return a < 0.05 ? 'small' : a < 0.20 ? 'medium' : 'large';
}

function macroEventStr(name: string, actual: number | null, prev: number | null, unit = '%'): string {
  if (actual == null) return '';
  const ps = prev != null ? `，前值 ${prev.toFixed(2)}${unit}` : '';
  const ss = prev != null ? `，surprise=${surpriseLabel(actual - prev)}` : '';
  return `${name}：实际 ${actual.toFixed(2)}${unit}${ps}${ss}`;
}

function scenarios(dateStr: string, yhat: number, lower: number, upper: number, support: number, resistance: number, trend: string): string[] {
  const d = dateStr.slice(0, 10);
  const dir = trend === 'up' ? '偏强' : '偏弱';
  return [
    `日期：${d}`,
    `基准：维持区间${dir}，预测 ${toFixed(yhat)}，区间 ${toFixed(lower)}-${toFixed(upper)}`,
    `风险上行：若突破 ${toFixed(resistance)}，可能向上试探`,
    `风险下行：若跌破 ${toFixed(support)}，可能继续回落`,
    `关键位：${toFixed(support)}, ${toFixed(resistance)}`,
  ];
}

const SRC_LINKS: Record<string, string[]> = {
  technical: ["本地XAUUSD行情快照", "TradingView XAUUSD 图表"],
  macro_yield: ["FRED - 2-Year Treasury Constant Maturity Rate", "BLS", "FRED", "BEA", "U.S. Treasury FiscalData"],
  macro_cpi: ["BLS", "FRED", "BEA", "FRED: U.S. 10Y Treasury yield", "FRED: U.S. 2Y Treasury yield"],
  news_foreign: ["Federal Reserve Press Releases", "BLS", "FRED", "BEA", "U.S. Treasury FiscalData"],
  news_cn: ["Jin10", "Jin10 Flash API", "Jin10 Flir Feed", "Sina Finance 7x24"],
};

const SRC_URLS: Record<string, string> = {
  "TradingView XAUUSD 图表": "https://www.tradingview.com/symbols/XAUUSD/",
  "FRED - 2-Year Treasury Constant Maturity Rate": "https://fred.stlouisfed.org/series/DGS2",
  "FRED: U.S. 10Y Treasury yield": "https://fred.stlouisfed.org/series/DGS10",
  "FRED: U.S. 2Y Treasury yield": "https://fred.stlouisfed.org/series/DGS2",
  "FRED: U.S. 10Y real yield": "https://fred.stlouisfed.org/series/DFII10",
  "BLS": "https://www.bls.gov/",
  "FRED": "https://fred.stlouisfed.org/",
  "BEA": "https://www.bea.gov/",
  "U.S. Treasury FiscalData": "https://fiscaldata.treasury.gov/",
  "Federal Reserve Press Releases": "https://www.federalreserve.gov/newsevents/pressreleases.htm",
  "Jin10": "https://www.jin10.com/",
  "Jin10 Flash API": "https://www.jin10.com/flash",
  "Jin10 Flir Feed": "https://www.jin10.com/",
  "Sina Finance 7x24": "https://finance.sina.com.cn/7x24/",
};

function linkHref(name: string): string | undefined {
  if (name === "本地XAUUSD行情快照") return "/dashboard";
  return SRC_URLS[name];
}

function techAnalysisText(vals: Record<string, number>, latestPrice: number): { overall: string; frames: string[] } {
  const rsi = vals.rsi14 ?? 50;
  const adx = vals.adx ?? 20;
  const macdLine = vals.macd_line ?? 0;
  const macdSignal = vals.macd_signal ?? 0;
  const ma20 = vals.ma20 ?? 0;
  const supertrend = vals.supertrend ?? 0;
  const supertrendDir = vals.supertrend_dir ?? 0;
  const bbLower = vals.bb_lower ?? 0;

  const bearishStruct = macdLine < macdSignal;
  const belowMa20 = ma20 > 0 && latestPrice < ma20;
  const sup = supertrend || bbLower;
  const nearSupport = sup > 0 && latestPrice < sup * 1.01;

  let overall = '';
  if (bearishStruct && belowMa20) {
    overall = '低点和高点结构仍偏弱，空头节奏未破坏；价格运行在压力带下方';
  } else if (bearishStruct) {
    overall = '空头动能占优，价格面临压力位压制';
  } else {
    overall = '低点逐步抬高，多头动能正在积累';
  }

  const h1 = rsi < 40 ? '1H 短线偏空' : rsi < 50 ? (adx < 25 ? '1H 短线震荡偏空' : '1H 短线偏空') : rsi < 60 ? (adx < 25 ? '1H 短线震荡' : '1H 短线偏多') : '1H 短线偏多';
  const h4 = bearishStruct && nearSupport ? '4H 若失守支撑，偏空延续' : !bearishStruct && supertrendDir > 0 ? '4H 支撑有效，短线企稳' : '4H 等待更多确认';
  const h8 = adx >= 25 ? `8H ${bearishStruct ? '空头' : '多头'}趋势运行中` : '8H 等待更多宏观确认';

  return { overall, frames: [h1, h4, h8].filter(Boolean) };
}

const riskEvents = [
  "本报告仅供研究参考，不构成投资建议。",
];

export default function Home() {
  const [loading, setLoading] = useState(true);
  const [signalLabel, setSignalLabel] = useState('加载中…');
  const [signalDesc, setSignalDesc] = useState('');
  const [metrics, setMetrics] = useState<MetricCardProps[]>([]);
  const [pills, setPills] = useState<string[]>([]);
  const [klineText, setKlineText] = useState('');
  const [macroItems, setMacroItems] = useState<string[]>([]);
  const [techHtml, setTechHtml] = useState('');
  const [techPills, setTechPills] = useState<string[]>([]);
  const [foreignNews, setForeignNews] = useState<{ title: string; link?: string }[]>([]);
  const [foreignSamples, setForeignSamples] = useState<{ title: string; date: string; link?: string }[]>([]);
  const [domesticNews, setDomesticNews] = useState<{ title: string; link?: string }[]>([]);
  const [domesticSamples, setDomesticSamples] = useState<{ title: string; date: string; link?: string }[]>([]);
  const [scenariosTomorrow, setScenariosTomorrow] = useState<string[]>([]);
  const [scenariosAfter, setScenariosAfter] = useState<string[]>([]);
  const [corePoints, setCorePoints] = useState<string[]>([]);
  const [reverseRisks, setReverseRisks] = useState<string[]>([]);
  const [referenceGroups, setReferenceGroups] = useState<{ title: string; links: string[] }[]>([]);

  useEffect(() => {
    Promise.allSettled([
      api.signal(),
      api.quick(),
      api.gold(),
      api.indicators(),
      api.macro(),
      api.news(),
      api.prediction(),
    ]).then(([signalRes, quickRes, goldRes, indRes, macroRes, newsRes, predRes]) => {
      let support = 4500;
      let resistance = 4770;
      let trend = 'down';

      let sigLabel = '';
      let sigDesc = '';
      let met: MetricCardProps[] = [];
      let pil: string[] = [];
      let kline = '';
      let tech = '';
      let techPil: string[] = [];
      const macItems: string[] = [];
      let cnNews: { title: string; link?: string }[] = [];
      let enNews: { title: string; link?: string }[] = [];
      const cnSamples: { title: string; date: string; link?: string }[] = [];
      const enSamples: { title: string; date: string; link?: string }[] = [];
      let scTom: string[] = [];
      let scAft: string[] = [];
      const core: string[] = [];
      let risks: string[] = [];

      // ── signal ──
      if (signalRes.status === 'fulfilled') {
        const s = signalRes.value.signal;
        const signal = s.signal || 'neutral';
        sigLabel = labelMap[signal] || '中性';
        sigDesc = `置信度 ${(s.confidence * 100).toFixed(0)}% · 得分 ${s.score}`;
        met = [
          { label: '多头概率', value: `${Math.max(0, s.score)}%`, tone: 'accent' },
          { label: '空头概率', value: `${Math.max(0, -s.score)}%`, tone: 'danger' },
          { label: '置信度', value: `${(s.confidence * 100).toFixed(0)}%`, tone: 'accent' },
          { label: '止盈/止损', value: `${toFixed(s.take_profit, 0)} / ${toFixed(s.stop_loss, 0)}`, tone: 'default' },
        ];
        pil = [
          `置信度 ${(s.confidence * 100).toFixed(0)}%`,
          `建议强度 ${signal === 'strong_sell' || signal === 'sell' ? '观望' : '关注'}`,
          `止损 ${toFixed(s.stop_loss, 0)} · 止盈 ${toFixed(s.take_profit, 0)}`,
          `市场状态 ${signal === 'sell' || signal === 'strong_sell' ? '下降趋势' : signal === 'buy' || signal === 'strong_buy' ? '上升趋势' : '震荡'}`,
        ];
        // derive trend for kline section
        trend = signal === 'sell' || signal === 'strong_sell' ? 'down' : signal === 'buy' || signal === 'strong_buy' ? 'up' : trend;
      }

      // ── gold + indicators (combined for kline generation) ──
      const gRecords = goldRes.status === 'fulfilled' ? goldRes.value.records : 0;

      // Generate multi-period K-line snapshot text
      if (goldRes.status === 'fulfilled' && goldRes.value.data.length > 0) {
        const goldData = goldRes.value.data;

        const periods = [
          { name: '1d', days: 1 },
          { name: '1w', days: 5 },
          { name: '1m', days: 22 },
          { name: '3m', days: 66 },
        ];

        const periodStats = periods.map(p => {
          const slice = goldData.slice(-p.days);
          const validPrices = slice.filter(d => d.close != null).map(d => d.close as number);
          if (validPrices.length === 0) return null;
          const high = Math.max(...validPrices);
          const low = Math.min(...validPrices);
          const first = validPrices[0];
          const last = validPrices[validPrices.length - 1];
          const trend = last < first ? '下降趋势' : '上升趋势';
          return `${p.name} ${trend} | 区间 ${low.toFixed(3)}-${high.toFixed(3)} | 支撑 ${low.toFixed(3)} | 压力 ${high.toFixed(3)} | 样本${validPrices.length}根`;
        }).filter(Boolean);

        kline = periodStats.join('\n');
      }

      if (indRes.status === 'fulfilled') {
        const ind = indRes.value;
        tech = '';
        if (ind.indicators) {
          const vals = ind.indicators;
          const price = ind.price ?? 0;
          const ta = techAnalysisText(vals, price);
          tech = ta.overall;
          support = vals.supertrend ?? vals.bb_lower ?? support;
          resistance = vals.bb_upper ?? vals.ma20 ?? resistance;
          const rangeLow = vals.bb_lower ?? support;
          const rangeHigh = vals.bb_upper ?? resistance;
          techPil = [...ta.frames, `RSI ${toFixed(vals.rsi)}`];
          if (vals.adx) techPil.push(`ADX ${toFixed(vals.adx)}`);
          if (vals.macd) techPil.push(`MACD ${toFixed(vals.macd)}`);
          techPil.push(`支撑 ${toFixed(support, 2)}`);
          techPil.push(`压力 ${toFixed(resistance, 2)}`);
        }
      }

      // ── macro ──
      if (macroRes.status === 'fulfilled') {
        const m = macroRes.value;
        const rtData = m.realtime?.data;
        if (rtData?.length) {
          const [actual10y, prev10y] = latestPair(rtData, 'us_10y');
          const [actual2y, prev2y] = latestPair(rtData, 'us_2y');
          const [actualVix, prevVix] = latestPair(rtData, 'vix');
          const s10y = macroEventStr('美国10年期收益率', actual10y, prev10y);
          const s2y = macroEventStr('美国2年期收益率', actual2y, prev2y);
          const sVix = actualVix != null ? `VIX：${actualVix.toFixed(2)}${prevVix != null ? `（前值 ${prevVix.toFixed(2)}）` : ''}` : '';
          if (s10y) macItems.push(s10y);
          if (s2y) macItems.push(s2y);
          if (sVix) macItems.push(sVix);
        }
        const ofData = m.official?.data;
        if (ofData?.length) {
          const [actualTips, prevTips] = latestPair(ofData, 'tips_yield');
          const [actualCpi, prevCpi] = latestPair(ofData, 'cpi');
          const [actualFed, prevFed] = latestPair(ofData, 'fed_rate');
          const sTips = macroEventStr('美国10年期实际收益率', actualTips, prevTips);
          const sCpi = macroEventStr('CPI', actualCpi, prevCpi);
          const sFed = macroEventStr('联邦基金利率', actualFed, prevFed);
          if (sTips) macItems.push(sTips);
          if (sCpi) macItems.push(sCpi);
          if (sFed) macItems.push(sFed);
        }
      }

      // ── news ──
      const DOMESTIC_SOURCES = ['hexun_gold', 'eastmoney', 'google_news_cn'];
      if (newsRes.status === 'fulfilled') {
        const n = newsRes.value;
        for (const item of n.news) {
          const entry = { title: item.title, date: item.published || item.published_date || '', link: item.link };
          if (DOMESTIC_SOURCES.includes(item.source)) cnSamples.push(entry);
          else enSamples.push(entry);
        }
        cnNews = cnSamples.slice(0, 3).map(x => ({ title: x.title, link: x.link }));
        enNews = enSamples.slice(0, 4).map(x => ({ title: x.title, link: x.link }));
      }

      // ── prediction ──
      if (predRes.status === 'fulfilled') {
        const p = predRes.value;
        trend = p.trend || trend;
        const fc = p.prediction || [];
        if (fc.length >= 1) scTom = scenarios(fc[0].ds, fc[0].yhat, fc[0].yhat_lower, fc[0].yhat_upper, support, resistance, trend);
        if (fc.length >= 2) scAft = scenarios(fc[1].ds, fc[1].yhat, fc[1].yhat_lower, fc[1].yhat_upper, support, resistance, trend);
      }

      // ── quick (debate markdown summary) ──
      if (quickRes.status === 'fulfilled') {
        const q = quickRes.value;
        if (q.signal) {
          if (q.signal.reasons) core.push(...q.signal.reasons.slice(0, 4));
          core.push(`信号强度: ${labelMap[q.signal.signal] || q.signal.signal}`);
        }
        if (q.indicators) {
          const lines = q.indicators.split('\n').filter((l: string) => l.trim().startsWith('-'));
          core.push(...lines.slice(0, 4).map((l: string) => l.replace(/^[-*]\s*/, '')));
        }
        if (q.signal?.reasons) {
          const riskLines = q.signal.reasons.filter((r: string) => /(空|回落|阻力|下行|弱)/.test(r));
          risks = riskLines.length > 0 ? riskLines.slice(0, 3) : q.signal.reasons.slice(0, 3);
        }
      }

      // ── reference groups (dynamic titles from actual data) ──
      const refs: { title: string; links: string[] }[] = [];
      refs.push({ title: kline || '实时行情', links: SRC_LINKS.technical });
      if (macItems.length > 0) {
        refs.push({ title: macItems.slice(0, 2).join('；'), links: SRC_LINKS.macro_yield });
        const rest = macItems.slice(2).join('；');
        if (rest) refs.push({ title: rest, links: SRC_LINKS.macro_cpi });
      }
      if (enSamples.length > 0) refs.push({ title: `已采集 ${enSamples.length} 条标准化国外新闻`, links: SRC_LINKS.news_foreign });
      if (cnSamples.length > 0) refs.push({ title: `已采集 ${cnSamples.length} 条标准化国内新闻`, links: SRC_LINKS.news_cn });
      if (macItems.length > 0) refs.push({ title: `已纳入 ${macItems.length} 条宏观数据`, links: SRC_LINKS.macro_cpi });
      core.slice(0, 3).forEach((pt) => {
        refs.push({ title: pt, links: SRC_LINKS.technical });
      });

      // ── batch all state updates ──
      setSignalLabel(sigLabel);
      setSignalDesc(sigDesc);
      setMetrics(met);
      setPills(pil);
      setKlineText(kline);
      setTechHtml(tech);
      setTechPills(techPil);
      setMacroItems(macItems);
      setForeignNews(enNews);
      setForeignSamples(enSamples);
      setDomesticNews(cnNews);
      setDomesticSamples(cnSamples);
      setScenariosTomorrow(scTom);
      setScenariosAfter(scAft);
      setCorePoints(core);
      setReverseRisks(risks);
      setReferenceGroups(refs);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <main className="min-h-screen">
        <div className="dashboard-shell">
          <div className="flex items-center justify-center py-24">
            <p className="muted-copy">加载分析报告…</p>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen">
      <div className="dashboard-shell">
        <section
          className="paper-card paper-card-strong reveal-card relative grid gap-6 p-5 md:grid-cols-[1.15fr_3.35fr] md:p-7"
          style={{ animationDelay: "40ms" }}
        >
          <div className="absolute top-4 right-5 md:top-5 md:right-7">
            <Link href="/dashboard" className="text-sm muted-copy hover:text-[var(--accent)] transition-colors">
              数据面板 ↗
            </Link>
          </div>
          <div className="rounded-[24px] bg-[rgba(255,253,247,0.7)] p-4 md:p-5">
            <p className="eyebrow">Gold AI</p>
            <h1 className="mt-3 font-display text-4xl leading-none md:text-[3.2rem]">{signalLabel}</h1>
            <p className="mt-3 text-lg muted-copy">{signalDesc}</p>
          </div>

          <div>
            <div className="grid gap-4 md:grid-cols-4">
              {metrics.map((metric) => (
                <MetricCard key={metric.label} {...metric} />
              ))}
            </div>

            <div className="mt-5 flex flex-wrap gap-2.5">
              {pills.map((pill) => (
                <span key={pill} className="data-pill">
                  {pill}
                </span>
              ))}
            </div>
          </div>
        </section>

        <div className="mt-4 grid gap-4 xl:grid-cols-[1.34fr_1fr]">
          <SectionCard title="多周期K线快照" delay={130}>
            {klineText ? (
              <ul className="list-disc report-list space-y-1">
                {klineText.split('\n').map((line, i) => (
                  <li key={i}>{line}</li>
                ))}
              </ul>
            ) : (
              <p className="muted-copy">暂无行情数据</p>
            )}
          </SectionCard>
          <SectionCard title="宏观事件摘要" delay={150}>
            <ul className="list-disc report-list space-y-1">
              {macroItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </SectionCard>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-[1.34fr_1fr]">
          <div className="flex flex-col gap-4">
            <SectionCard title="技术面" delay={170}>
              <p className="text-sm">{techHtml || '暂无数据'}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {techPills.map((pill) => (
                  <span key={pill} className="data-pill">{pill}</span>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="国外宏观" delay={210}>
              {foreignNews.length > 0 ? (
                <ul className="list-disc report-list space-y-1">
                  {foreignNews.map((item) => (
                    <li key={item.title}>
                      {item.link ? (
                        <a href={item.link} target="_blank" rel="noopener noreferrer" className="inline-link">{item.title}</a>
                      ) : (
                        item.title
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted-copy">暂无国外宏观新闻</p>
              )}
            </SectionCard>

            <SectionCard title="国内新闻" delay={250}>
              {domesticNews.length > 0 ? (
                <ul className="list-disc report-list space-y-1">
                  {domesticNews.map((item) => (
                    <li key={item.title}>
                      {item.link ? (
                        <a href={item.link} target="_blank" rel="noopener noreferrer" className="inline-link">{item.title}</a>
                      ) : (
                        item.title
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted-copy">暂无国内新闻</p>
              )}
            </SectionCard>

            <SectionCard title="国外新闻明细（本次样本）" delay={290}>
              {foreignSamples.length > 0 ? (
                <ul className="list-disc report-list space-y-3">
                  {foreignSamples.slice(0, 6).map((item) => (
                    <li key={item.title}>
                      {item.link ? (
                        <a href={item.link} target="_blank" rel="noopener noreferrer" className="inline-link">{item.title}</a>
                      ) : (
                        <span className="inline-link">{item.title}</span>
                      )}
                      <p className="mt-1 text-sm muted-copy">{item.date}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted-copy">暂无国外新闻明细</p>
              )}
            </SectionCard>

            <SectionCard title="国内新闻明细（本次样本）" delay={330}>
              {domesticSamples.length > 0 ? (
                <ul className="list-disc report-list space-y-3">
                  {domesticSamples.slice(0, 8).map((item) => (
                    <li key={item.title}>
                      {item.link ? (
                        <a href={item.link} target="_blank" rel="noopener noreferrer" className="inline-link">{item.title}</a>
                      ) : (
                        <span className="inline-link">{item.title}</span>
                      )}
                      <p className="mt-1 text-sm muted-copy">{item.date}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted-copy">暂无国内新闻明细</p>
              )}
            </SectionCard>

            <SectionCard title="明日三情景" delay={370}>
              {scenariosTomorrow.length > 0 ? (
                <ul className="list-disc report-list space-y-1">
                  {scenariosTomorrow.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted-copy">暂无情景数据（预测接口不可用）</p>
              )}
            </SectionCard>

            <SectionCard title="后日三情景" delay={410} className="grow">
              {scenariosAfter.length > 0 ? (
                <ul className="list-disc report-list space-y-1">
                  {scenariosAfter.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted-copy">暂无情景数据（预测接口不可用）</p>
              )}
            </SectionCard>
          </div>

          <div className="flex flex-col gap-4 h-full">
            <SectionCard title="核心依据" delay={190}>
              {corePoints.length > 0 ? (
                <ul className="list-disc report-list space-y-1">
                  {corePoints.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted-copy">暂无核心依据（分析接口不可用）</p>
              )}
            </SectionCard>

            <SectionCard title="核心依据参考链接" delay={230}>
              <ul className="list-disc report-list space-y-3">
                {referenceGroups.map((group) => (
                  <li key={group.title}>
                    <span className="font-medium">{group.title}</span>
                    <ul className="list-disc report-list mt-1 ml-4 space-y-1 text-[var(--accent)]">
                      {group.links.map((link) => {
                        const href = linkHref(link);
                        return (
                          <li key={link}>
                            {href ? (
                              <a href={href} target="_blank" rel="noopener noreferrer" className="inline-link">{link}</a>
                            ) : (
                              <span className="muted-copy">{link}</span>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </li>
                ))}
              </ul>
            </SectionCard>

            <SectionCard title="反向风险" delay={270}>
              {reverseRisks.length > 0 ? (
                <ul className="list-disc report-list space-y-1">
                  {reverseRisks.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted-copy">暂无风险提示</p>
              )}
            </SectionCard>

            <SectionCard title="风险事件" delay={310} className="grow">
              <ul className="list-disc report-list space-y-1">
                {riskEvents.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </SectionCard>
          </div>
        </div>
      </div>
    </main>
  );
}
