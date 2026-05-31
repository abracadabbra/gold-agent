/**
 * @jest-environment jsdom
 */

describe('getCached', () => {
  it('returns null for uncached key', () => {
    const { getCached } = jest.requireActual('@/lib/api');
    expect(getCached('nonexistent')).toBeNull();
  });

  it('returns data when within TTL', async () => {
    jest.resetModules();
    const data = { status: 'ok' };
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => data,
      text: async () => JSON.stringify(data),
    });
    const { api, getCached } = await import('@/lib/api');
    await api.health();
    const cached = getCached<any>('GET:http://localhost:8001/health');
    expect(cached).toEqual(data);
  });
});

function createModule() {
  return jest.requireActual('@/lib/api') as typeof import('@/lib/api');
}

describe('api', () => {
  let fetchMock: jest.Mock;

  beforeEach(() => {
    fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok', version: '0.1.0' }),
      text: async () => '{"status":"ok","version":"0.1.0"}',
    });
    global.fetch = fetchMock;
    jest.resetModules();
  });

  it('health calls /health', async () => {
    const { api } = createModule();
    await api.health();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/health'),
      expect.anything(),
    );
  });

  it('stats calls /stats', async () => {
    const { api } = createModule();
    await api.stats();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/stats'),
      expect.anything(),
    );
  });

  it('gold builds correct URL', async () => {
    const { api } = createModule();
    await api.gold('shfe', '1mo');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/analysis/gold?source=shfe&period=1mo'),
      expect.anything(),
    );
  });

  it('indicators builds correct URL', async () => {
    const { api } = createModule();
    await api.indicators('intl', '1y');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/analysis/indicators?source=intl&period=1y'),
      expect.anything(),
    );
  });

  it('signal builds correct URL', async () => {
    const { api } = createModule();
    await api.signal();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/analysis/signal'),
      expect.anything(),
    );
  });

  it('prediction builds correct URL', async () => {
    const { api } = createModule();
    await api.prediction('intl', 14);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/analysis/predict?source=intl&days=14'),
      expect.anything(),
    );
  });

  it('macro builds correct URL', async () => {
    const { api } = createModule();
    await api.macro('6mo');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/analysis/macro?period=6mo'),
      expect.anything(),
    );
  });

  it('news calls correct path', async () => {
    const { api } = createModule();
    await api.news();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/analysis/news'),
      expect.anything(),
    );
  });

  it('debate uses POST method', async () => {
    const { api } = createModule();
    await api.debate();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/debate/run'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('quick calls correct path', async () => {
    const { api } = createModule();
    await api.quick();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/debate/quick'),
      expect.anything(),
    );
  });

  it('strategies calls correct path', async () => {
    const { api } = createModule();
    await api.strategies();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/backtest/strategies'),
      expect.anything(),
    );
  });

  it('backtest builds correct URL', async () => {
    const { api } = createModule();
    await api.backtest('golden_cross', '3y', 50000);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        '/api/backtest/run?strategy=golden_cross&period=3y&initial_cash=50000',
      ),
      expect.anything(),
    );
  });

  it('calendar builds correct URL', async () => {
    const { api } = createModule();
    await api.calendar(30);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/analysis/calendar?days=30'),
      expect.anything(),
    );
  });

  it('factors calls correct path', async () => {
    const { api } = createModule();
    await api.factors();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/analysis/factors'),
      expect.anything(),
    );
  });

  it('deduplicates concurrent requests', async () => {
    let callCount = 0;
    global.fetch = jest.fn().mockImplementation(async () => {
      await new Promise(r => setTimeout(r, 10));
      callCount++;
      return { ok: true, json: async () => ({ status: 'ok' }), text: async () => '{"status":"ok"}' };
    });

    const { api } = createModule();
    const [r1, r2] = await Promise.all([api.health(), api.health()]);
    expect(r1).toEqual(r2);
    expect(callCount).toBe(1);
  });

  it('throws on HTTP error with body', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: async () => 'Internal Server Error',
    });

    const { api } = createModule();
    await expect(api.health()).rejects.toThrow('HTTP 500 — Internal Server Error');
  });

  it('extraData builds correct URL', async () => {
    const { api } = createModule();
    await api.extraData();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/analysis/extra'),
      expect.anything(),
    );
  });
});
