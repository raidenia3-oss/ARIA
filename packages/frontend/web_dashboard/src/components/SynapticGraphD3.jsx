import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

const NODES = [
  { id: 'C-01', label: 'Santuario', group: 'core' },
  { id: 'C-02', label: 'Pulso', group: 'core' },
  { id: 'C-03', label: 'Resonancia', group: 'core' },
  { id: 'C-04', label: 'Sentencia', group: 'core' },
  { id: 'M-01', label: 'Frontend', group: 'module' },
  { id: 'M-02', label: 'Backend', group: 'module' },
  { id: 'M-03', label: 'WebRTC', group: 'module' },
  { id: 'M-04', label: 'Swarm', group: 'module' },
]

const LINKS = [
  { source: 'C-01', target: 'C-02' },
  { source: 'C-01', target: 'C-03' },
  { source: 'C-02', target: 'C-04' },
  { source: 'C-03', target: 'C-04' },
  { source: 'C-01', target: 'M-01' },
  { source: 'C-02', target: 'M-02' },
  { source: 'C-03', target: 'M-03' },
  { source: 'C-04', target: 'M-04' },
  { source: 'M-01', target: 'M-02' },
  { source: 'M-02', target: 'M-03' },
  { source: 'M-03', target: 'M-04' },
]

export default function SynapticGraphD3() {
  const svgRef = useRef()

  useEffect(() => {
    const svg = d3.select(svgRef.current)
    const width = svgRef.current.clientWidth
    const height = 320

    svg.selectAll('*').remove()

    const g = svg.append('g').attr('transform', 'translate(0, 10)')

    const simulation = d3.forceSimulation(NODES)
      .force('link', d3.forceLink(LINKS).id(d => d.id).distance(60))
      .force('charge', d3.forceManyBody().strength(-120))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(18))

    const link = g.append('g')
      .selectAll('line')
      .data(LINKS)
      .join('line')
      .attr('stroke', 'rgba(56, 189, 248, 0.35)')
      .attr('stroke-width', 1.2)

    const node = g.append('g')
      .selectAll('g')
      .data(NODES)
      .join('g')
      .call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        }))

    node.append('circle')
      .attr('r', d => d.group === 'core' ? 8 : 5)
      .attr('fill', d => d.group === 'core' ? '#38bdf8' : '#6366f1')
      .attr('stroke', '#0a0f14')
      .attr('stroke-width', 1.5)

    node.append('text')
      .text(d => d.label)
      .attr('x', 10)
      .attr('y', 3)
      .attr('fill', '#e2e8f0')
      .attr('font-size', '9px')
      .attr('font-family', 'ui-sans-serif, system-ui')
      .attr('font-weight', 600)
      .attr('letter-spacing', '0.05em')

    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)

      node.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    return () => {
      simulation.stop()
    }
  }, [])

  return (
    <svg
      ref={svgRef}
      className="h-[320px] w-full"
      viewBox="0 0 500 320"
      preserveAspectRatio="xMidYMid meet"
    />
  )
}
