import React, { useEffect, useRef } from 'react'
import * as d3 from 'd3'

const SANCTUARY_NODES = [
  { id: 'C-01', name: 'Sanctuary', color: '#6366f1', type: 'core' },
  { id: 'C-02', name: 'Pulse', color: '#06b6d4', type: 'core' },
  { id: 'C-03', name: 'Resonance', color: '#ec4899', type: 'core' },
  { id: 'C-04', name: 'Sentencia', color: '#f59e0b', type: 'core' },
]

const AGENT_NODES = Array.from({ length: 8 }, (_, i) => ({
  id: `A-${String(i + 1).padStart(2, '0')}`,
  name: `Agent ${i + 1}`,
  color: '#10b981',
  type: 'agent',
}))

export default function SynapticGraph({ theme, telemetry }) {
  const containerRef = useRef(null)
  const svgRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current) return

    const nodes = [...SANCTUARY_NODES, ...AGENT_NODES]
    
    const links = []
    // Create links from cores to agents
    SANCTUARY_NODES.forEach((core) => {
      AGENT_NODES.forEach((agent, idx) => {
        if (idx % 2 === SANCTUARY_NODES.indexOf(core) % 2) {
          links.push({ source: core.id, target: agent.id, type: 'control' })
        }
      })
    })

    const width = containerRef.current.clientWidth
    const height = containerRef.current.clientHeight

    // Clear previous SVG
    d3.select(svgRef.current).selectAll('*').remove()

    const svg = d3
      .select(svgRef.current)
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height])

    // Define arrowhead marker
    svg
      .append('defs')
      .append('marker')
      .attr('id', 'arrowhead')
      .attr('markerWidth', 10)
      .attr('markerHeight', 10)
      .attr('refX', 9)
      .attr('refY', 3)
      .attr('orient', 'auto')
      .append('polygon')
      .attr('points', '0 0, 10 3, 0 6')
      .attr('fill', theme)

    // Create simulation
    const simulation = d3
      .forceSimulation(nodes)
      .force('link', d3.forceLink(links).id((d) => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))

    // Draw links
    const link = svg
      .append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', `rgba(${hexToRgb(theme).join(',')}, 0.3)`)
      .attr('stroke-width', 2)
      .attr('marker-end', 'url(#arrowhead)')

    // Draw nodes
    const node = svg
      .append('g')
      .selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('r', (d) => (d.type === 'core' ? 12 : 8))
      .attr('fill', (d) => d.color)
      .attr('stroke', (d) => `rgba(${hexToRgb(d.color).join(',')}, 0.5)`)
      .attr('stroke-width', 2)
      .call(
        d3
          .drag()
          .on('start', dragStarted)
          .on('drag', dragged)
          .on('end', dragEnded)
      )

    // Add labels
    const label = svg
      .append('g')
      .selectAll('text')
      .data(nodes)
      .join('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.31em')
      .attr('font-size', '11px')
      .attr('fill', '#e0e8ff')
      .attr('font-weight', '600')
      .text((d) => d.id)

    // Update positions on simulation tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y)

      node.attr('cx', (d) => d.x).attr('cy', (d) => d.y)

      label.attr('x', (d) => d.x).attr('y', (d) => d.y)
    })

    // Drag functions
    function dragStarted(event, d) {
      if (!event.active) simulation.alphaTarget(0.3).restart()
      d.fx = d.x
      d.fy = d.y
    }

    function dragged(event, d) {
      d.fx = event.x
      d.fy = event.y
    }

    function dragEnded(event, d) {
      if (!event.active) simulation.alphaTarget(0)
      d.fx = null
      d.fy = null
    }

    // Interaction: click node to highlight
    node.on('click', (event, d) => {
      node.attr('opacity', (n) =>
        n.id === d.id || links.some((l) => l.source.id === d.id || l.target.id === d.id)
          ? 1
          : 0.3
      )
      link.attr('opacity', (l) =>
        l.source.id === d.id || l.target.id === d.id ? 1 : 0.1
      )
    })

    // Reset on background click
    svg.on('click', () => {
      node.attr('opacity', 1)
      link.attr('opacity', 1)
    })

    return () => {
      simulation.stop()
    }
  }, [theme])

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: '100%',
        background: 'linear-gradient(135deg, rgba(10,14,39,0.5) 0%, rgba(22,27,58,0.5) 100%)',
      }}
    >
      <svg ref={svgRef} style={{ width: '100%', height: '100%' }} />
    </div>
  )
}

function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  return result
    ? [
        parseInt(result[1], 16),
        parseInt(result[2], 16),
        parseInt(result[3], 16),
      ]
    : [99, 102, 241]
}
