import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { GraphExplorer } from './GraphExplorer';

// Mock Clerk
vi.mock('@clerk/clerk-react', () => ({
  useAuth: () => ({ getToken: vi.fn().mockResolvedValue('test-token') }),
}));

// Mock fetch for graph endpoints
const mockNodes = { nodes: ['TSMC', 'NVIDIA', 'ASML'] };
const mockEdges = {
  edges: [{ source: 'ASML', target: 'TSMC', relation: 'supplies', weight: 0.95 }],
};

describe('GraphExplorer', () => {
  beforeEach(() => {
    global.fetch = vi.fn((url: string) => {
      if (url.includes('/graph/nodes')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockNodes) } as Response);
      }
      if (url.includes('/graph/edges')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockEdges) } as Response);
      }
      return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) } as unknown as Response);
    }) as unknown as typeof fetch;
  });

  it('renders loading then graph', async () => {
    render(<GraphExplorer />);
    expect(screen.getByText(/Loading supply-chain graph/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/Supply-Chain Graph Explorer/i)).toBeInTheDocument());
    expect(screen.getByText(/3 nodes/i)).toBeInTheDocument();
  });

  it('shows legend and svg', async () => {
    render(<GraphExplorer />);
    await waitFor(() => expect(screen.getByText(/Supply-Chain Graph Explorer/i)).toBeInTheDocument());
    expect(document.querySelector('svg')).toBeInTheDocument();
    expect(screen.getAllByText(/fab/i).length).toBeGreaterThan(0);
  });

  it('handles fetch error', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as unknown as Response)) as unknown as typeof fetch;
    render(<GraphExplorer />);
    await waitFor(() => expect(screen.getByText(/Graph load failed/i)).toBeInTheDocument());
  });
});
