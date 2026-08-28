import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';
import * as d3 from 'd3';
import { BASE_URL } from '../api/siliconpulseApi';
import { Network, RefreshCw, Sparkles } from 'lucide-react';

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

// Premium enterprise palette — dark navy, restrained, fab-inspired
const GROUP_COLOR: Record<GraphNode['group'], string> = {
  fab: '#38BDF8', // EUV cyan — equipment / fab
  chip: '#F59E0B', // wafer amber — silicon / chips
  cloud: '#10B981', // yield green — hyperscalers / AI labs
  other: '#94A3B8',
};

const GROUP_LABEL: Record<GraphNode['group'], string> = {
  fab: 'Equipment & Fab',
  chip: 'Silicon',
  cloud: 'Cloud & AI',
  other: 'Other',
};

export const GraphExplorer: React.FC<GraphExplorerProps> = ({ onSelectCompany, selectedCompany, className }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { getToken } = useAuth();
  const [data, setData] = useState<GraphData | null>(null);
  const [selected, setSelected] = useState<string | null>(selectedCompany ?? null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
      if (!nodesRes.ok || !edgesRes.ok) throw new Error(`Graph fetch failed: ${nodesRes.status}/${edgesRes.status}`);
      const nodesJson: { nodes: string[] } = await nodesRes.json();
      const edgesJson: { edges: Array<{ source: string; target: string; relation: string; weight: number }> } = await edgesRes.json();
      setData({ nodes: nodesJson.nodes.map((id) => ({ id })), edges: edgesJson.edges });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load graph');
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  // Premium D3 rendering
  useEffect(() => {
    if (!data || !svgRef.current || !containerRef.current) return;

    const svgEl = svgRef.current;
    const width = containerRef.current.clientWidth || 760;
    const height = 480;

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

    // Build adjacency for hover
    const adjacency = new Map<string, Set<string>>();
    links.forEach((l) => {
      const s = typeof l.source === 'string' ? l.source : (l.source as GraphNode).id;
      const t = typeof l.target === 'string' ? l.target : (l.target as GraphNode).id;
      if (!adjacency.has(s)) adjacency.set(s, new Set());
      if (!adjacency.has(t)) adjacency.set(t, new Set());
      adjacency.get(s)!.add(t);
      adjacency.get(t)!.add(s);
    });

    const svg = d3.select(svgEl);
    svg.selectAll('*').remove();
    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .attr('preserveAspectRatio', 'xMidYMid meet')
      .style('background', '#020617');

    // --- Defs: gradients, filters, markers ---
    const defs = svg.append('defs');

    // Subtle grid pattern for enterprise depth (very low opacity)
    defs
      .append('pattern')
      .attr('id', 'premiumGrid')
      .attr('width', 32)
      .attr('height', 32)
      .attr('patternUnits', 'userSpaceOnUse')
      .append('path')
      .attr('d', 'M 32 0 L 0 0 0 32')
      .attr('fill', 'none')
      .attr('stroke', '#1E293B')
      .attr('stroke-width', 0.5)
      .attr('opacity', 0.35);

    // Soft glow filters per group
    const glowColors: Record<GraphNode['group'], string> = {
      fab: '#38BDF8',
      chip: '#F59E0B',
      cloud: '#10B981',
      other: '#64748B',
    };
    (Object.keys(glowColors) as GraphNode['group'][]).forEach((g) => {
      const f = defs.append('filter').attr('id', `glow-${g}`).attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%');
      f.append('feGaussianBlur').attr('stdDeviation', '4').attr('result', 'coloredBlur');
      const merge = f.append('feMerge');
      merge.append('feMergeNode').attr('in', 'coloredBlur');
      merge.append('feMergeNode').attr('in', 'SourceGraphic');
    });

    // Node halo filter (selected)
    const halo = defs.append('filter').attr('id', 'halo').attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%');
    halo.append('feGaussianBlur').attr('stdDeviation', '6').attr('result', 'blur');
    halo.append('feColorMatrix').attr('type', 'matrix').attr('values', '1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 0.6 0');

    // Arrow markers - premium: slightly larger, rounded, matching hairline
    const markerColors: Record<string, string> = { default: '#475569', highlight: '#E2E8F0' };
    Object.entries(markerColors).forEach(([key, color]) => {
      defs
        .append('marker')
        .attr('id', `arrow-${key}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 22)
        .attr('refY', 0)
        .attr('markerWidth', 7)
        .attr('markerHeight', 7)
        .attr('orient', 'auto')
        .attr('markerUnits', 'strokeWidth')
        .append('path')
        .attr('d', 'M0,-4 L9,0 L0,4 L2,0 Z')
        .attr('fill', color)
        .attr('stroke', color)
        .attr('stroke-width', 0.5)
        .attr('stroke-linejoin', 'round');
    });

    // Radial gradients for nodes (depth)
    (Object.entries(GROUP_COLOR) as [GraphNode['group'], string][]).forEach(([group, color]) => {
      const grad = defs.append('radialGradient').attr('id', `grad-${group}`).attr('cx', '35%').attr('cy', '30%').attr('r', '75%');
      grad.append('stop').attr('offset', '0%').attr('stop-color', d3.color(color)!.brighter(0.6).formatHex());
      grad.append('stop').attr('offset', '55%').attr('stop-color', color);
      grad.append('stop').attr('offset', '100%').attr('stop-color', d3.color(color)!.darker(0.55).formatHex());
    });

    const g = svg.append('g');

    // Background grid rect
    g.append('rect').attr('width', width).attr('height', height).attr('fill', 'url(#premiumGrid)').attr('opacity', 0.18).lower();
    g.append('rect').attr('width', width).attr('height', height).attr('fill', 'none').attr('stroke', '#0F172A').attr('stroke-width', 0).lower();

    // Subtle vignette
    const vignette = defs.append('radialGradient').attr('id', 'vignette').attr('cx', '50%').attr('cy', '50%').attr('r', '75%');
    vignette.append('stop').attr('offset', '70%').attr('stop-color', '#020617').attr('stop-opacity', 0);
    vignette.append('stop').attr('offset', '100%').attr('stop-color', '#020617').attr('stop-opacity', 0.55);
    g.append('rect').attr('width', width).attr('height', height).attr('fill', 'url(#vignette)').attr('pointer-events', 'none');

    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.45, 3.2])
      .on('zoom', (event: d3.D3ZoomEvent<SVGSVGElement, unknown>) => g.attr('transform', event.transform.toString()));
    try {
      svg.call(zoom as unknown as (selection: d3.Selection<SVGSVGElement, unknown, null, undefined>) => void);
    } catch {
      // jsdom lacks SVG baseVal — zoom disabled in tests
    }
    // Set initial subtle zoom (guarded for jsdom where baseVal is undefined)
    try {
      svg.call(
        zoom.transform as unknown as (selection: d3.Selection<SVGSVGElement, unknown, null, undefined>, transform: d3.ZoomTransform) => void,
        d3.zoomIdentity.scale(0.98).translate(6, 4)
      );
    } catch {
      // jsdom doesn't support SVG baseVal — safe to ignore in tests
    }

    // --- Simulation: balanced, intentional layout ---
    const simulation = d3
      .forceSimulation<GraphNode>(nodes as GraphNode[])
      .force('link', d3.forceLink<GraphNode, GraphLink>(links as unknown as GraphLink[]).id((d: GraphNode) => d.id).distance((d: GraphLink) => 88 + (1 - d.weight) * 42).strength((d: GraphLink) => 0.38 + d.weight * 0.32))
      .force('charge', d3.forceManyBody<GraphNode>().strength(-520))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide<GraphNode>(54).strength(0.92))
      .force('y', d3.forceY(height / 2).strength(0.06))
      .force('x', d3.forceX(width / 2).strength(0.04))
      .alphaDecay(0.022);

    // Anchor TSMC slightly central for hierarchy (foundry hub)
    const tsmc = nodes.find((n) => n.id === 'TSMC');
    if (tsmc) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (tsmc as any).fx = width * 0.52;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (tsmc as any).fy = height * 0.46;
      setTimeout(() => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (tsmc as any).fx = null;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (tsmc as any).fy = null;
        simulation.alpha(0.12).restart();
      }, 1400);
    }

    // --- Links: premium hairline with weight hierarchy ---
    const link = g
      .append('g')
      .attr('fill', 'none')
      .attr('stroke-linecap', 'round')
      .selectAll('path')
      .data(links)
      .join('path')
      .attr('stroke', '#334155')
      .attr('stroke-opacity', 0.72)
      .attr('stroke-width', (d) => (d.weight >= 0.85 ? 1.9 : d.weight >= 0.7 ? 1.45 : 1.1))
      .attr('marker-end', 'url(#arrow-default)')
      .style('transition', 'stroke 180ms ease, stroke-opacity 180ms ease, stroke-width 180ms ease');

    // Subtle link glow on hover (via class)
    // --- Link relation pills ---
    const linkGroup = g.append('g').selectAll('g').data(links).join('g').attr('pointer-events', 'none');

    const linkPill = linkGroup
      .append('rect')
      .attr('rx', 7)
      .attr('ry', 7)
      .attr('fill', '#0F172A')
      .attr('stroke', '#1E293B')
      .attr('stroke-width', 0.9)
      .attr('height', 13)
      .attr('y', -6.5)
      .attr('opacity', 0.96);

    const linkLabel = linkGroup
      .append('text')
      .attr('font-size', '8px')
      .attr('font-weight', '600')
      .attr('font-family', 'Inter, ui-sans-serif, system-ui')
      .attr('letter-spacing', '0.02em')
      .attr('fill', '#94A3B8')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('y', 0.5)
      .text((d) => d.relation);

    // Measure pills after render (guarded for jsdom)
    linkGroup.each(function () {
      const txt = d3.select(this).select('text').node() as SVGTextElement | null;
      const rect = d3.select(this).select('rect').node() as SVGRectElement | null;
      if (txt && rect) {
        let w = 40;
        try {
          w = typeof (txt as unknown as { getComputedTextLength?: () => number }).getComputedTextLength === 'function'
            ? (txt as unknown as { getComputedTextLength: () => number }).getComputedTextLength()
            : (txt.textContent?.length ?? 6) * 5.5;
        } catch {
          w = (txt.textContent?.length ?? 6) * 5.5;
        }
        const pad = 10;
        d3.select(rect).attr('width', w + pad).attr('x', -(w + pad) / 2);
      }
    });

    // --- Nodes: premium enterprise nodes ---
    const color = d3
      .scaleOrdinal<GraphNode['group'], string>()
      .domain(['fab', 'chip', 'cloud', 'other'])
      .range(Object.values(GROUP_COLOR));

    const nodeGroup = g.append('g').selectAll('g').data(nodes).join('g').attr('cursor', 'pointer').style('filter', (d) => `url(#glow-${d.group})`);

    // Outer subtle halo for depth (non-interactive)
    nodeGroup
      .append('circle')
      .attr('r', (d) => (d.id === 'TSMC' || d.id === 'NVIDIA' ? 20 : d.id === 'Microsoft' || d.id === 'ASML' ? 16 : 13.5))
      .attr('fill', 'none')
      .attr('stroke', (d) => color(d.group))
      .attr('stroke-width', 0.9)
      .attr('opacity', 0.14)
      .attr('class', 'halo');

    // Main node with gradient
    const node = nodeGroup
      .append('circle')
      .attr('r', (d) => (d.id === 'TSMC' || d.id === 'NVIDIA' ? 15.5 : d.id === 'Microsoft' || d.id === 'ASML' ? 12.5 : 10.5))
      .attr('fill', (d) => `url(#grad-${d.group})`)
      .attr('stroke', (d) => (selected === d.id ? '#F1F5F9' : 'rgba(241,245,249,0.92)'))
      .attr('stroke-width', (d) => (selected === d.id ? 2.2 : 1.15))
      .attr('stroke-opacity', (d) => (selected === d.id ? 1 : 0.92))
      .style('filter', (d) => (selected === d.id ? 'url(#halo)' : 'none'))
      .attr('class', 'node-core');

    // Inner highlight dot for depth
    nodeGroup
      .append('circle')
      .attr('r', (d) => (d.id === 'TSMC' || d.id === 'NVIDIA' ? 4.2 : 3))
      .attr('cx', -2.2)
      .attr('cy', -2.2)
      .attr('fill', 'white')
      .attr('opacity', 0.18)
      .attr('pointer-events', 'none');

    // Selection ring (extra)
    const selectRing = nodeGroup
      .append('circle')
      .attr('r', (d) => (d.id === 'TSMC' || d.id === 'NVIDIA' ? 19 : 14))
      .attr('fill', 'none')
      .attr('stroke', '#F1F5F9')
      .attr('stroke-width', 1.2)
      .attr('stroke-opacity', (d) => (selected === d.id ? 0.85 : 0))
      .attr('stroke-dasharray', '3 3')
      .attr('pointer-events', 'none')
      .style('transition', 'stroke-opacity 200ms ease');

    node.append('title').text((d) => `${d.id} — ${GROUP_LABEL[d.group]}`);

    // Node labels — premium pill with cleaner contrast
    const labelGroup = g.append('g').selectAll('g').data(nodes).join('g').attr('pointer-events', 'none');

    const labelBg = labelGroup
      .append('rect')
      .attr('rx', 6)
      .attr('ry', 6)
      .attr('fill', '#0B1220')
      .attr('stroke', '#1E293B')
      .attr('stroke-width', 0.85)
      .attr('height', 16)
      .attr('y', 18)
      .attr('opacity', 0.96);

    const labelText = labelGroup
      .append('text')
      .attr('font-size', '10.5px')
      .attr('font-weight', '650')
      .attr('font-family', 'Inter, ui-sans-serif, system-ui')
      .attr('letter-spacing', '-0.01em')
      .attr('fill', '#F1F5F9')
      .attr('text-anchor', 'middle')
      .attr('y', 29)
      .text((d) => d.id);

    labelGroup.each(function () {
      const txt = d3.select(this).select('text').node() as SVGTextElement | null;
      const bg = d3.select(this).select('rect').node() as SVGRectElement | null;
      if (txt && bg) {
        let w = 60;
        try {
          w = typeof (txt as unknown as { getComputedTextLength?: () => number }).getComputedTextLength === 'function'
            ? (txt as unknown as { getComputedTextLength: () => number }).getComputedTextLength()
            : (txt.textContent?.length ?? 8) * 6.2;
        } catch {
          w = (txt.textContent?.length ?? 8) * 6.2;
        }
        const pad = 10;
        d3.select(bg).attr('width', w + pad).attr('x', -(w + pad) / 2);
      }
    });

    // Hover interaction — highlight connected, dim others
    const updateHighlight = (hoveredId: string | null) => {
      const focusId = hoveredId ?? selected;
      if (!focusId) {
        // Reset
        nodeGroup.style('opacity', 1);
        labelGroup.style('opacity', 1);
        link.style('opacity', 1).attr('stroke', '#334155').attr('marker-end', 'url(#arrow-default)').attr('stroke-opacity', 0.72);
        linkGroup.style('opacity', 1);
        node.attr('stroke-opacity', (d: GraphNode) => (selected === d.id ? 1 : 0.92));
        selectRing.attr('stroke-opacity', (d: GraphNode) => (selected === d.id ? 0.85 : 0));
        return;
      }
      const neighbors = adjacency.get(focusId) ?? new Set<string>();
      const isConnected = (id: string) => id === focusId || neighbors.has(id);
      const isLinkConnected = (l: GraphLink) => {
        const s = typeof l.source === 'string' ? l.source : (l.source as GraphNode).id;
        const t = typeof l.target === 'string' ? l.target : (l.target as GraphNode).id;
        return s === focusId || t === focusId;
      };

      nodeGroup
        .transition()
        .duration(180)
        .style('opacity', (d: GraphNode) => (isConnected(d.id) ? 1 : 0.18))
        .style('filter', (d: GraphNode) => (isConnected(d.id) ? `url(#glow-${d.group})` : 'none'));

      labelGroup.transition().duration(180).style('opacity', (d: GraphNode) => (isConnected(d.id) ? 1 : 0.22));

      link
        .transition()
        .duration(180)
        .style('opacity', (d: GraphLink) => (isLinkConnected(d) ? 1 : 0.12))
        .attr('stroke', (d: GraphLink) => (isLinkConnected(d) ? '#64748B' : '#334155'))
        .attr('marker-end', (d: GraphLink) => (isLinkConnected(d) ? 'url(#arrow-highlight)' : 'url(#arrow-default)'))
        .attr('stroke-opacity', (d: GraphLink) => (isLinkConnected(d) ? 0.95 : 0.18));

      linkGroup.transition().duration(180).style('opacity', (d: GraphLink) => (isLinkConnected(d) ? 1 : 0.14));

      // Keep selected ring visible
      selectRing.attr('stroke-opacity', (d: GraphNode) => (d.id === focusId ? 0.9 : selected === d.id ? 0.4 : 0));
    };

    // Attach hover handlers to node groups
    nodeGroup
      .on('mouseenter', (_event, d: GraphNode) => updateHighlight(d.id))
      .on('mouseleave', () => updateHighlight(null))
      .on('click', (_event, d: GraphNode) => {
        const next = d.id;
        setSelected(next);
        onSelectCompany?.(next);
        updateHighlight(next);
      })
      .call(
        d3
          .drag<SVGGElement, GraphNode>()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.28).restart();
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
          }) as unknown as (selection: d3.Selection<SVGGElement, GraphNode, SVGGElement, unknown>) => void
      );

    // Initial highlight if selected
    if (selected) updateHighlight(selected);

    // Curved links for premium feel — use path with gentle arc to reduce overlap
    const linkArc = (d: GraphLink) => {
      const s = d.source as GraphNode;
      const t = d.target as GraphNode;
      if (s.x == null || s.y == null || t.x == null || t.y == null) return '';
      const dx = t.x - s.x;
      const dy = t.y - s.y;
      const dr = Math.sqrt(dx * dx + dy * dy) * 1.18;
      // Alternate curvature direction by relation hash to avoid overlapping bidirectional
      const hash = d.relation.charCodeAt(0) % 2 === 0 ? 1 : -1;
      return `M${s.x},${s.y} A${dr},${dr} 0 0,${hash === 1 ? 1 : 0} ${t.x},${t.y}`;
    };

    simulation.on('tick', () => {
      link.attr('d', linkArc);

      // Position pills at mid-point with offset perpendicular for readability
      linkGroup.attr('transform', (d: GraphLink) => {
        const s = d.source as GraphNode;
        const t = d.target as GraphNode;
        if (s.x == null || s.y == null || t.x == null || t.y == null) return '';
        const mx = (s.x + t.x) / 2;
        const my = (s.y + t.y) / 2;
        // Slight perpendicular offset to avoid sitting exactly on curved path
        const dx = t.x - s.x;
        const dy = t.y - s.y;
        const len = Math.sqrt(dx * dx + dy * dy) || 1;
        const nx = -dy / len;
        const ny = dx / len;
        const offset = ((d.relation.charCodeAt(0) % 3) - 1) * 6; // -6,0,6 staggered
        return `translate(${mx + nx * offset},${my + ny * offset})`;
      });

      nodeGroup.attr('transform', (d: GraphNode) => `translate(${d.x ?? 0},${d.y ?? 0})`);
      labelGroup.attr('transform', (d: GraphNode) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    // Resize
    const ro = new ResizeObserver(() => {
      const w = containerRef.current?.clientWidth ?? width;
      simulation.force('center', d3.forceCenter(w / 2, height / 2));
      svg.attr('viewBox', `0 0 ${w} ${height}`);
      g.select('rect').attr('width', w);
      simulation.alpha(0.18).restart();
    });
    if (containerRef.current) ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      simulation.stop();
    };
  }, [data, selected, onSelectCompany]);

  if (loading) {
    return (
      <div className={`rounded-[16px] border border-[#1E293B]/60 bg-[#0B1220]/60 backdrop-blur p-6 ${className ?? ''}`}>
        <div className="flex items-center gap-2 text-[#64748B] text-xs">
          <span className="h-2 w-2 rounded-full bg-[#38BDF8] animate-pulse" />
          <span className="uppercase tracking-[0.12em] font-semibold text-[10px]">Loading supply-chain graph…</span>
        </div>
        <div className="mt-4 h-[480px] rounded-xl bg-[#020617]/60 border border-[#1E293B]/40 animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className={`rounded-[16px] border border-red-500/15 bg-red-500/[0.06] p-4 ${className ?? ''}`}>
        <div className="flex items-center justify-between gap-3">
          <p className="text-[12px] leading-relaxed text-red-300">Graph load failed: {error}</p>
          <button onClick={fetchGraph} className="inline-flex items-center gap-1.5 rounded-full bg-[#0B1220] border border-[#1E293B] px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.08em] text-[#94A3B8] hover:text-white hover:border-[#334155] transition-colors">
            <RefreshCw size={12} /> Retry
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className={`space-y-3 ${className ?? ''}`}>
      {/* Premium header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.14em] text-[#E2E8F0]">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#38BDF8]/10 border border-[#38BDF8]/20">
              <Network size={12} className="text-[#38BDF8]" />
            </span>
            Supply-Chain Graph Explorer
            <span className="hidden sm:inline-flex items-center gap-1 rounded-full bg-[#E8A253]/10 border border-[#E8A253]/15 px-2 py-0.5 text-[9px] font-bold tracking-[0.08em] text-[#F59E0B]">
              <Sparkles size={10} /> PREMIUM
            </span>
          </h3>
          <p className="mt-1 max-w-[560px] text-[11px] leading-relaxed text-[#64748B]">Enterprise topology • 19 verified relationships • Hover to isolate impact paths</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden md:inline-flex items-center rounded-full bg-[#0B1220] border border-[#1E293B] px-2.5 py-1 text-[10px] font-medium tracking-[0.02em] text-[#64748B]">
            {data.nodes.length} nodes • {data.edges.length} edges
          </span>
          <button onClick={fetchGraph} className="inline-flex items-center gap-1.5 rounded-full bg-[#0B1220] border border-[#1E293B] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-[#94A3B8] hover:text-white hover:border-[#334155] hover:bg-[#0F172A] transition-colors">
            <RefreshCw size={12} /> Refresh
          </button>
        </div>
      </div>

      {/* Legend — restrained */}
      <div className="flex flex-wrap gap-1.5">
        {(Object.entries(GROUP_LABEL) as [GraphNode['group'], string][]).map(([key, label]) => (
          <span key={key} className="inline-flex items-center gap-1.5 rounded-full border border-[#1E293B] bg-[#0B1220]/70 px-2.5 py-1 text-[10px] font-semibold tracking-[0.04em] text-[#CBD5E1]">
            <span className="h-2 w-2 rounded-full shadow-[0_0_8px_currentColor]" style={{ background: GROUP_COLOR[key], color: GROUP_COLOR[key] }} />
            {label}
          </span>
        ))}
        <span className="ml-auto hidden sm:inline-flex items-center gap-1 text-[10px] font-medium text-[#475569]">
          Drag to reposition • Scroll to zoom • Click to select
        </span>
      </div>

      <div
        ref={containerRef}
        className="group relative overflow-hidden rounded-[16px] border border-[#1E293B] bg-[#020617] shadow-[0_10px_40px_rgba(2,6,23,0.55),inset_0_1px_0_rgba(255,255,255,0.04)]"
      >
        {/* Top hairline glow */}
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[#38BDF8]/25 to-transparent" />
        <svg ref={svgRef} width="100%" height={480} className="block" role="img" aria-label="Supply chain graph" />
        {/* Bottom fade for depth */}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-[#020617]/60 to-transparent" />
      </div>

      {selected ? (
        <div className="flex flex-wrap items-center gap-2 rounded-[12px] border border-[#38BDF8]/15 bg-[#38BDF8]/[0.06] px-3.5 py-2.5 text-[12px] leading-relaxed text-[#BAE6FD]">
          <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-[#38BDF8] text-[10px] font-black text-[#020617]">{selected.slice(0, 1)}</span>
          <span>
            Selected <span className="font-bold text-white">{selected}</span>
          </span>
          <span className="hidden sm:inline text-[#7DD3FC]/60">— isolated to connected relationships • Use sidebar Scenario Engine to simulate shocks</span>
        </div>
      ) : (
        <p className="text-center text-[11px] leading-relaxed text-[#475569]">Hover any node to highlight its supply chain • Selected nodes sync to the sidebar Graph RAG panel</p>
      )}
    </div>
  );
};
