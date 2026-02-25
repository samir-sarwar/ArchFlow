import type { CanvasNode, CanvasConnection, NodeType } from '@/types/diagram';

const SHAPE_WRAPPERS: Record<NodeType, [string, string]> = {
  service: ['[', ']'],
  database: ['[(', ')]'],
  cache: ['((', '))'],
  loadbalancer: ['{', '}'],
  custom: ['[', ']'],
};

/**
 * Generate flowchart Mermaid syntax from canvas nodes and connections.
 */
export function generateMermaidFlowchart(
  nodes: CanvasNode[],
  connections: CanvasConnection[],
  direction: 'TD' | 'LR' = 'TD'
): string {
  if (nodes.length === 0) return '';

  const lines: string[] = [`graph ${direction}`];

  // Node definitions
  for (const node of nodes) {
    const [open, close] = SHAPE_WRAPPERS[node.type] || SHAPE_WRAPPERS.custom;
    lines.push(`    ${node.id}${open}${node.label}${close}`);
  }

  // Connection definitions
  for (const conn of connections) {
    if (conn.label) {
      lines.push(`    ${conn.sourceId} -->|${conn.label}| ${conn.targetId}`);
    } else {
      lines.push(`    ${conn.sourceId} --> ${conn.targetId}`);
    }
  }

  return lines.join('\n');
}
