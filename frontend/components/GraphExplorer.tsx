import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';
import * as d3 from 'd3';
import { BASE_URL } from '../api/siliconpulseApi';
import { Network, Maximize2, RefreshCw } from 'lucide-react';

// Types matching backend graph/store.py
interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  group: 'fab' | 'chip' | 'cloud' | 'other';
}

interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
  source: string | GraphNode;
  target: string | GraphNode;
  relation: string;
  weight: number;
}

interface GraphData {
  nodes: { id: string }[];
  edges: { source: string; target: string; relation: string; weight: number }[];
}

interface GraphExplorerProps {
  onSelectCompany?: (company: string) => void;
  selectedCompany?: string | null;
  className?: string;
}

const GROUP_FOR = (id: string): GraphNode['group'] => {
  if (id === 'TSMC' || id === 'ASML' || id === 'Samsung' || id === 'Applied Materials' || id === 'Lam Research') return 'fab';
  if (id === 'NVIDIA' || id === 'AMD' || id === 'Intel' || id === 'Micron') return 'chip';
  if (id === 'Microsoft' || id === 'Google' || id === 'Meta' || id === 'Amazon' || id === 'Anthropic' || id === 'OpenAI') return 'cloud';
  return 'other';
};

const GROUP_COLOR: Record<GraphNode['group'], string> = {
  fab: '#38bdf8',
  chip: '#f59e0b',
  cloud: '#10b981',
  other: '#94a3b8',
};

export const GraphExplorer: React.FC<GraphExplorerProps> = ({ onSelectCompany, selectedCompany, className }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { getToken } = useAuth();
  const [data, setData] = useState<GraphData | null>(null);
  const [selected, setSelected] = useState<string | null>(selectedCompany ?? null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Sync external selection
  useEffect(() => {
    if (selectedCompany !== undefined) setSelected(selectedCompany);
  }, [selectedCompany]);

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken().catch(() => null);
      const headers: Record<string, string> = {};
      if (token) headers.Authorization = `Bearer ${token}`;

      const [nodesRes, edgesRes] = await Promise.all([
        fetch(`${BASE_URL}/graph/nodes`, { headers }),
        fetch(`${BASE_URL}/graph/edges`, { headers }),
      ]);

      if (!nodesRes.ok || !edgesRes.ok) {
        throw new Error(`Graph fetch failed: ${nodesRes.status}/${edgesRes.status}`);
      }

      const nodesJson: { nodes: string[] } = await nodesRes.json();
      const edgesJson: { edges: Array<{ source: string; target: string; relation: string; weight: number }> } =
        await edgesRes.json();

      setData({
        nodes: nodesJson.nodes.map((id) => ({ id })),
        edges: edgesJson.edges,
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to load graph';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  // D3 rendering
  useEffect(() => {
    if (!data || !svgRef.current || !containerRef.current) return;

    const svgEl = svgRef.current;
    const width = containerRef.current.clientWidth || 700;
    const height = 420;

    const nodes: GraphNode[] = data.nodes.map((n) => ({
      id: n.id,
      group: GROUP_FOR(n.id),
    }));

    const links: GraphLink[] = data.edges.map((e) => ({
      source: e.source,
      target: e.target,
      relation: e.relation,
      weight: e.weight,
    }));

    const svg = d3.select(svgEl);
    svg.selectAll('*').remove();
    svg.attr('viewBox', `0 0 ${width} ${height}`).attr('preserveAspectRatio', 'xMidYMid meet');

    const g = svg.append('g');

    // Zoom / pan
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.4, 4])
      .on('zoom', (event: d3.D3ZoomEvent<SVGSVGElement, unknown>) => {
        g.attr('transform', event.transform.toString());
      });
    svg.call(zoom as unknown as (selection: d3.Selection<SVGSVGElement, unknown, null, undefined>) => void);

    // Defs for arrow markers
    svg
      .append('defs')
      .append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 22)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#334155');

    const simulation = d3
      .forceSimulation<GraphNode>(nodes as GraphNode[])
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .force('link', d3.forceLink<GraphNode, GraphLink>(links as any).id((d: GraphNode) => d.id).distance(95).strength(0.55))
      .force('charge', d3.forceManyBody<GraphNode>().strength(-320))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide<GraphNode>(42));

    // Links
    const link = g
      .append('g')
      .attr('stroke-linecap', 'round')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', '#334155')
      .attr('stroke-opacity', 0.7)
      .attr('stroke-width', (d) => Math.max(1.2, d.weight * 3.2))
      .attr('marker-end', 'url(#arrow)');

    // Link labels (relation)
    const linkLabel = g
      .append('g')
      .selectAll('text')
      .data(links)
      .join('text')
      .attr('font-size', '7px')
      .attr('font-weight', '600')
      .attr('fill', '#64748b')
      .attr('text-anchor', 'middle')
      .attr('paint-order', 'stroke')
      .attr('stroke', '#020617')
      .attr('stroke-width', '3px')
      .attr('stroke-linejoin', 'round')
      .text((d) => d.relation)
      .style('pointer-events', 'none');

    const color = d3.scaleOrdinal<GraphNode['group'], string>().domain(['fab', 'chip', 'cloud', 'other']).range(Object.values(GROUP_COLOR));

    // Nodes
    const node = g
      .append('g')
      .selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('r', (d) => (d.id === 'TSMC' || d.id === 'NVIDIA' ? 15 : 11))
      .attr('fill', (d) => color(d.group))
      .attr('stroke', (d) => (selected === d.id ? '#ffffff' : '#0f172a'))
      .attr('stroke-width', (d) => (selected === d.id ? 2.5 : 1.6))
      .attr('cursor', 'pointer')
      .call(
        d3
          .drag<SVGCircleElement, GraphNode>()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            (d as GraphNode & { fx?: number; fy?: number }).fx = (d as GraphNode).x;
            (d as GraphNode & { fx?: number; fy?: number }).fy = (d as GraphNode).y;
          })
          .on('drag', (event, d) => {
            (d as GraphNode & { fx?: number; fy?: number }).fx = event.x;
            (d as GraphNode & { fx?: number; fy?: number }).fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            (d as GraphNode & { fx?: number | null; fy?: number | null }).fx = null;
            (d as GraphNode & { fx?: number | null; fy?: number | null }).fy = null;
          }) as unknown as (selection: d3.Selection<SVGCircleElement, GraphNode, SVGGElement, unknown>) => void
      )
      .on('click', (_event, d) => {
        const next = d.id;
        setSelected(next);
        onSelectCompany?.(next);
      });

    node.append('title').text((d) => `${d.id} (${d.group})`);

    // Labels under nodes
    const label = g
      .append('g')
      .selectAll('text')
      .data(nodes)
      .join('text')
      .attr('font-size', '9.5px')
      .attr('font-weight', '800')
      .attr('fill', '#e2e8f0')
      .attr('text-anchor', 'middle')
      .attr('dy', 26)
      .text((d) => d.id)
      .style('pointer-events', 'none')
      .style('text-shadow', '0 1px 3px rgba(0,0,0,0.9)');

    simulation.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as GraphNode).x ?? 0)
        .attr('y1', (d) => (d.source as GraphNode).y ?? 0)
        .attr('x2', (d) => (d.target as GraphNode).x ?? 0)
        .attr('y2', (d) => (d.target as GraphNode).y ?? 0);

      linkLabel
        .attr('x', (d) => (((d.source as GraphNode).x ?? 0) + ((d.target as GraphNode).x ?? 0)) / 2)
        .attr('y', (d) => (((d.source as GraphNode).y ?? 0) + ((d.target as GraphNode).y ?? 0)) / 2);

      node.attr('cx', (d) => (d as GraphNode).x ?? 0).attr('cy', (d) => (d as GraphNode).y ?? 0);
      label.attr('x', (d) => (d as GraphNode).x ?? 0).attr('y', (d) => (d as GraphNode).y ?? 0);
    });

    // Resize observer for responsiveness
    const ro = new ResizeObserver(() => {
      const w = containerRef.current?.clientWidth ?? width;
      simulation.force('center', d3.forceCenter(w / 2, height / 2));
      simulation.alpha(0.2).restart();
    });
    if (containerRef.current) ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      simulation.stop();
    };
  }, [data, selected, onSelectCompany]);

  if (loading) {
    return (
      <div className={`rounded-2xl border border-slate-800/60 bg-slate-950/40 p-6 ${className ?? ''}`}>
        <div className="flex items-center space-x-2 text-slate-500 text-xs animate-pulse">
          <Network size={14} />
          <span className="uppercase tracking-widest font-black text-[10px]">Loading supply-chain graph…</span>
        </div>
        <div className="mt-4 h-[420px] rounded-xl bg-slate-900/40 animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className={`rounded-2xl border border-red-500/20 bg-red-500/10 p-4 ${className ?? ''}`}>
        <div className="flex items-center justify-between">
          <p className="text-xs text-red-400 font-medium">Graph load failed: {error}</p>
          <button
            onClick={fetchGraph}
            className="inline-flex items-center space-x-1 rounded bg-slate-900 px-2 py-1 text-[10px] font-black uppercase tracking-widest text-slate-300 hover:bg-slate-800"
          >
            <RefreshCw size={12} />
            <span>Retry</span>
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className={`space-y-3 ${className ?? ''}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center space-x-2 text-[11px] font-black uppercase tracking-widest text-sky-400">
          <Network size={12} />
          <span>Supply-Chain Graph Explorer</span>
        </h3>
        <div className="flex items-center gap-3 text-[10px]">
          <span className="text-slate-500">
            {data.nodes.length} nodes • {data.edges.length} edges
          </span>
          <span className="hidden sm:inline-flex items-center gap-1 text-slate-600">
            <Maximize2 size={10} /> drag • scroll to zoom
          </span>
          <button
            onClick={fetchGraph}
            className="inline-flex items-center gap-1 rounded border border-slate-800 bg-slate-900 px-2 py-1 text-[10px] font-bold uppercase tracking-widest text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            title="Reload graph"
          >
            <RefreshCw size={10} /> Refresh
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 text-[10px] font-bold">
        {(['fab', 'chip', 'cloud', 'other'] as const).map((g) => (
          <span key={g} className="inline-flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-900/60 px-2.5 py-1 uppercase tracking-widest">
            <span className="h-2 w-2 rounded-full" style={{ background: GROUP_COLOR[g] }} />
            <span className="text-slate-400">{g}</span>
          </span>
        ))}
      </div>

      <div
        ref={containerRef}
        className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 shadow-[0_0_30px_rgba(2,132,199,0.08)]"
      >
        <svg ref={svgRef} width="100%" height={420} className="block bg-slate-950" role="img" aria-label="Supply chain graph" />
      </div>

      {selected ? (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-sky-500/20 bg-sky-500/10 px-3 py-2 text-xs text-sky-200">
          <span>
            Selected: <span className="font-black text-white">{selected}</span>
          </span>
          <span className="text-sky-300/60">— click another node to focus. Use the sidebar Graph RAG panel to run scenario shocks on this company.</span>
        </div>
      ) : (
        <p className="text-[11px] text-slate-500">Click a node to select a company. Drag to reposition, scroll to zoom, and combine with the Scenario Engine.</p>
      )}
    </div>
  );
};
