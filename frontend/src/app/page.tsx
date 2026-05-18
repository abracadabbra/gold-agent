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

const topMetrics = [
  { label: "多头概率", value: "40%", tone: "accent" as const },
  { label: "空头概率", value: "45%", tone: "danger" as const },
  { label: "中性概率", value: "15%", tone: "accent" as const },
  { label: "预计区间", value: "4501.035-\n4772.385", tone: "default" as const },
];

const statusPills = [
  "置信度 中",
  "建议强度 观望",
  "市场状态 下降趋势",
  "事件模式 普通交易日",
  "状态 开市中",
  "开市 周一 06:00 (北京时间)",
  "休市 周六 05:00 (北京时间)",
  "距开市 20小时19分钟",
  "距休市 19小时19分钟",
];

const macroSummary = [
  "美国10年期收益率，实际 4.35%，前值 4.36%，surprise=medium，priced_in=medium",
  "美国2年期收益率，实际 3.78%，前值 3.84%，surprise=medium，priced_in=medium",
  "美国10年期实际收益率，实际 1.91%，前值 1.92%，surprise=medium，priced_in=medium",
];

const keyPoints = [
  "低点和高点结构仍偏弱，空头节奏未被破坏",
  "价格仍运行在附近压力带下方",
  "U.S. 2Y yield fell to 3.78% from 3.84%, reducing short-rate pressure and opportunity cost for gold.",
  "U.S. 10Y yield edged down to 4.35% from 4.36%, a small supportive move for non-yielding gold.",
  "现货黄金突破4530美元，纽约期金涨0.30%",
  "已采集 6 条标准化国外新闻",
  "已采集 9 条标准化国内新闻",
  "已纳入 6 条带有实际值/预期值语境的宏观事件",
];

const foreignNews = [
  "U.S. 2Y yield fell to 3.78% from 3.84%, reducing short-rate pressure and opportunity cost for gold；U.S. 10Y yield edged down to 4.35% from 4.36%, a small supportive move for non-yielding gold.",
  "FRED U.S. 10Y Treasury yield latest 4.35%, previous 4.36%。更高的美债实际收益率通常会通过机会成本压制现货黄金；U.S. 2Y Treasury yield latest 3.78%, previous 3.84%。更高的美债实际收益率通常会通过机会成本压制现货黄金。",
  "BEA U.S. personal consumption expenditures latest 11183323%，previous 11212669%。消费韧性可能强化通胀黏性并推迟美联储降息，通常偏空黄金；U.S. personal income latest 391771%，previous 393682%。收入走弱可能维持需求韧性，并强化高利率维持更久的叙事。",
  "U.S. Treasury Treasury Bills latest 3.702%，previous 3.212%。更高的财政融资成本和利率，可能通过收益率与美元预期压制黄金。",
];

const foreignSamples = [
  "FRED: U.S. 10Y Treasury yield",
  "FRED: U.S. 2Y Treasury yield",
  "FRED: U.S. 10Y real yield",
  "BEA: U.S. personal consumption expenditures",
  "BEA: U.S. personal income",
  "U.S. Treasury: Treasury Bills",
];

const domesticNews = [
  "现货黄金突破4530美元，纽约期金涨0.30%；美联储三把手偏鹰表态，降息方向未变",
];

const domesticSamples = [
  "Jin10 Flash: 现货黄金向上触及 4530 美元/盎司，日内涨0.14%。",
  "Jin10 Flash: 国内金易购均价实时抢价，数至北京时间09:30，纽约期金涨0.30%，纽约期银跌0.38%，纽约铜涨0.50%。",
  "Jin10 News: 美联储三把手发声：若通胀回落到终值路径上，时点已被迫延后。",
  "Jin10 News: 美国至水木夜行动将在几小时内开始，航运巨头反而更慌了？",
  "Sina Finance 7x24: 现货黄金突破4530美元/盎司，日内涨0.15%。",
  "Sina Finance 7x24: 占中东东部场景压力释放与原油联动，市场对美联储与外需复苏预期维持拉扯。",
  "Sina Finance 7x24: 纽约铜产量波动，美股中东紧张局势再度升高，贵金属避险需求略有抬升。",
];

const scenariosTomorrow = [
  "日期：2026-05-06",
  "基准：维持区间偏弱，优先观察 4501.035-4772.385 内下沿压力。",
  "风险升级：若地缘/避险事件升级，金价更可能向上试探并站稳 4772.385 上方。",
  "风险缓和：若收益率与美元同步走强，金价更可能回落并测试 4501.035 附近支撑。",
  "关键位：4501.035, 4772.385",
  "依据链接：本地XAUUSD行情快照；TradingView XAUUSD 图表；FRED - 2-Year Treasury Constant Maturity Rate；BLS；FRED；BEA；U.S. Treasury FiscalData",
];

const scenariosAfter = [
  "日期：2026-05-07",
  "基准：维持区间偏弱，继续观察 4501.035-4772.385 内下沿压力。",
  "风险升级：若地缘/避险事件升级，金价更可能向上试探并站稳 4772.385 上方。",
  "风险缓和：若收益率与美元同步走强，金价更可能回落并测试 4501.035 附近支撑。",
  "关键位：4501.035, 4772.385",
  "依据链接：本地XAUUSD行情快照；TradingView XAUUSD 图表；FRED - 2-Year Treasury Constant Maturity Rate；BLS；FRED；BEA；U.S. Treasury FiscalData",
];

const referenceGroups = [
  {
    title: "低点和高点结构仍偏弱，空头节奏未被破坏",
    links: ["本地XAUUSD行情快照", "TradingView XAUUSD 图表"],
  },
  {
    title: "价格仍运行在附近压力带下方",
    links: ["本地XAUUSD行情快照", "TradingView XAUUSD 图表"],
  },
  {
    title: "U.S. 2Y yield fell to 3.78% from 3.84%",
    links: ["FRED - 2-Year Treasury Constant Maturity Rate", "BLS", "FRED", "BEA", "U.S. Treasury FiscalData"],
  },
  {
    title: "U.S. 10Y yield edged down to 4.35% from 4.36%",
    links: ["BLS", "FRED", "BEA", "U.S. Treasury FiscalData"],
  },
  {
    title: "现货黄金突破4530美元，纽约期金涨0.30%",
    links: ["FRED: U.S. 10Y Treasury yield", "FRED: U.S. 2Y Treasury yield", "FRED: U.S. 10Y real yield"],
  },
  {
    title: "已采集 6 条标准化国外新闻",
    links: ["Federal Reserve Press Releases", "BLS", "FRED", "BEA", "U.S. Treasury FiscalData"],
  },
  {
    title: "已采集 9 条标准化国内新闻",
    links: ["Jin10", "Jin10 Flash API", "Jin10 Flir Feed", "Sina Finance 7x24"],
  },
  {
    title: "已纳入 6 条带有实际值/预期值语境的宏观事件",
    links: ["BLS", "FRED", "BEA", "FRED: U.S. 10Y Treasury yield", "FRED: U.S. 2Y Treasury yield"],
  },
];

const reverseRisks = [
  "存在空头回补引发反弹的风险",
  "Treasury bill rate jumped to 3.702% from 3.212%, signaling tighter front-end rate conditions that can support the dollar and pressure gold.",
  "美元或由中东事件走强，压制黄金",
];

const riskEvents = [
  "BLS: HTTPSConnectionPool(host='api.bls.gov', port=443): Max retries exceeded with url: /publicAPI/v2/timeseries/data/ (Caused by SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1016)')))",
  "Foreign news coverage acquired from 5 source clients",
  "Macro event items in current batch: 6",
  "Domestic news coverage acquired with 9 normalized items",
  "Live multi-timeframe candles acquired from TradingView: 1d",
  "Probability mode: ai_only (rule-based fusion temporarily bypassed)",
  "本报告仅供研究参考，不构成投资建议。",
];

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

export default function Home() {
  return (
    <main className="min-h-screen">
      <div className="dashboard-shell">
        <section
          className="paper-card paper-card-strong reveal-card grid gap-6 p-5 md:grid-cols-[1.15fr_3.35fr] md:p-7"
          style={{ animationDelay: "40ms" }}
        >
          <div className="rounded-[24px] bg-[rgba(255,253,247,0.7)] p-4 md:p-5">
            <p className="eyebrow">Gold AI</p>
            <h1 className="mt-3 font-display text-4xl leading-none md:text-[3.2rem]">偏空</h1>
            <p className="mt-3 text-lg muted-copy">区间内偏弱运行</p>
          </div>

          <div>
            <div className="grid gap-4 md:grid-cols-4">
              {topMetrics.map((metric) => (
                <MetricCard key={metric.label} {...metric} />
              ))}
            </div>

            <div className="mt-5 flex flex-wrap gap-2.5">
              {statusPills.map((pill) => (
                <span key={pill} className="data-pill">
                  {pill}
                </span>
              ))}
            </div>
          </div>
        </section>

        <div className="mt-4 grid gap-4 xl:grid-cols-[1.34fr_1fr]">
          <SectionCard title="多周期K线快照" delay={90}>
            <ul className="report-list">
              <li>
                1D 下降趋势｜区间 4501.035-4772.385｜支撑 4501.035｜压力 4772.385｜样本 10 根
              </li>
            </ul>
          </SectionCard>

          <SectionCard title="宏观事件摘要" delay={130}>
            <ul className="report-list space-y-1">
              {macroSummary.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </SectionCard>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-[1.34fr_1fr]">
          <div className="space-y-4">
            <SectionCard title="技术面" delay={170}>
              <p>
                低点和高点结构仍偏弱，空头节奏未被破坏；价格仍运行在附近压力带下方
              </p>
              <div className="mt-4 flex flex-wrap gap-2.5">
                {["1H 短线震荡偏空", "4H 若失守支撑，偏空延续", "8H 等待更多宏观确认", "支撑 4501.035", "压力 4772.385"].map((pill) => (
                  <span key={pill} className="data-pill">
                    {pill}
                  </span>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="国外宏观" delay={210}>
              <p>{foreignNews[0]}</p>
              <ul className="report-list mt-3 space-y-1">
                {foreignNews.slice(1).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </SectionCard>

            <SectionCard title="国内新闻" delay={250}>
              <p>{domesticNews[0]}</p>
            </SectionCard>

            <SectionCard title="国外新闻明细（本次样本）" delay={290}>
              <ul className="space-y-3">
                {foreignSamples.map((item) => (
                  <li key={item}>
                    <a href="#" className="inline-link">
                      {item}
                    </a>
                    <p className="mt-1 text-sm muted-copy">2026-04-27T00:00:00+00:00</p>
                  </li>
                ))}
              </ul>
            </SectionCard>

            <SectionCard title="国内新闻明细（本次样本）" delay={330}>
              <ul className="space-y-3">
                {domesticSamples.map((item, index) => (
                  <li key={item}>
                    <a href="#" className="inline-link">
                      {item}
                    </a>
                    <p className="mt-1 text-sm muted-copy">
                      2026-05-05T{String(7 + index).padStart(2, "0")}:3{index}:00+00:00
                    </p>
                  </li>
                ))}
              </ul>
            </SectionCard>

            <SectionCard title="明日三情景" delay={370}>
              <ul className="report-list space-y-1">
                {scenariosTomorrow.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </SectionCard>

            <SectionCard title="后日三情景" delay={410}>
              <ul className="report-list space-y-1">
                {scenariosAfter.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </SectionCard>
          </div>

          <div className="space-y-4">
            <SectionCard title="核心依据" delay={190}>
              <ul className="report-list space-y-1">
                {keyPoints.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </SectionCard>

            <SectionCard title="核心依据参考链接" delay={230}>
              <div className="space-y-4">
                {referenceGroups.map((group) => (
                  <div key={group.title}>
                    <p className="font-medium">{group.title}</p>
                    <ul className="report-list mt-1 space-y-1 text-[var(--accent)]">
                      {group.links.map((link) => (
                        <li key={link}>
                          <a href="#" className="inline-link">
                            {link}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="反向风险" delay={270}>
              <ul className="report-list space-y-1">
                {reverseRisks.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </SectionCard>

            <SectionCard title="风险事件" delay={310}>
              <ul className="report-list space-y-1">
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
