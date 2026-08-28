import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { GraphPanel } from './GraphPanel';

vi.mock('../api/siliconpulseApi', () => ({
  fetchGraphExplain: vi.fn().mockResolvedValue({
    company: 'TSMC',
    depth: 2,
    context: 'Supply-chain context for TSMC',
    impact: { NVIDIA: { score: 0.95 } },
    suppliers: { ASML: { score: 0.95 } },
  }),
  simulateGraph: vi.fn().mockResolvedValue({
    company: 'TSMC',
    shock: -0.1,
    impact: { NVIDIA: { delta: -0.095, est_impact_usd_m: 950, severity: 'Medium' } },
    impact_text: 'NVIDIA down',
    scenario_report: null,
  }),
}));

describe('GraphPanel', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders placeholder when no company', () => {
    render(<GraphPanel />);
    expect(screen.getByText(/Supply-Chain Graph/i)).toBeInTheDocument();
    expect(screen.getByText(/Select a company/i)).toBeInTheDocument();
  });

  it('renders graph data for company', async () => {
    render(<GraphPanel company="TSMC" />);
    await waitFor(() => expect(screen.getByText(/GRAPH RAG — TSMC/i)).toBeInTheDocument());
    expect(await screen.findByText(/Upstream/i)).toBeInTheDocument();
    expect(screen.getByText(/ASML/i)).toBeInTheDocument();
  });

  it('shows scenario controls when data loaded', async () => {
    render(<GraphPanel company="TSMC" />);
    await waitFor(() => expect(screen.getByText(/WHAT IF/i)).toBeInTheDocument(), { timeout: 3000 });
    expect(screen.getByRole('button', { name: /Simulate Shock/i })).toBeInTheDocument();
  });
});
