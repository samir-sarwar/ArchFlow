import type { CanvasNode, CanvasConnection, NodeType } from '@/types/diagram';

export interface ParseResult {
  nodes: CanvasNode[];
  connections: CanvasConnection[];
  direction: 'TD' | 'LR';
}

// Shape patterns and their corresponding node types
const SHAPE_PATTERNS: { regex: RegExp; type: NodeType }[] = [
  { regex: /^\[?\((.+?)\)\]?$/, type: 'database' },   // [(Label)] cylinder
  { regex: /^\(\((.+?)\)\)$/, type: 'cache' },          // ((Label)) circle
  { regex: /^\{(.+?)\}$/, type: 'loadbalancer' },       // {Label} diamond
  { regex: /^\[(.+?)\]$/, type: 'service' },             // [Label] rectangle
  { regex: /^\((.+?)\)$/, type: 'service' },             // (Label) rounded
];

/**
 * Parse flowchart Mermaid syntax into nodes and connections.
 * Handles: graph TD/LR, flowchart TD/LR
 */
export function parseMermaidFlowchart(syntax: string): ParseResult {
  const lines = syntax.split('\n').map((l) => l.trim()).filter(Boolean);

  if (lines.length === 0) {
    return { nodes: [], connections: [], direction: 'TD' };
  }

  // Detect direction from first line
  const headerMatch = lines[0].match(/^(?:graph|flowchart)\s+(TD|TB|LR|RL)/i);
  const direction: 'TD' | 'LR' = headerMatch
    ? headerMatch[1].toUpperCase() === 'LR' || headerMatch[1].toUpperCase() === 'RL'
      ? 'LR'
      : 'TD'
    : 'TD';

  const nodeMap = new Map<string, { label: string; type: NodeType }>();
  const connections: CanvasConnection[] = [];

  // Process each line (skip header)
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];

    // Skip comments and subgraph/end lines
    if (line.startsWith('%%') || line.startsWith('subgraph') || line === 'end') {
      continue;
    }

    // Try to parse as edge: A -->|label| B or A --> B
    const edgeMatch = line.match(
      /^(\w+)(?:\[.*?\]|\(.*?\)|\{.*?\})?\s*(-+[-.>|=]+(?:\|(.+?)\|)?-*>?)\s*(\w+)(?:\[.*?\]|\(.*?\)|\{.*?\})?$/
    );

    if (edgeMatch) {
      const [, sourceId, , edgeLabel, targetId] = edgeMatch;

      // Extract inline node definitions from source side
      const sourceInline = line.match(new RegExp(`^${sourceId}(\\[.*?\\]|\\(.*?\\)|\\{.*?\\})`));
      if (sourceInline && !nodeMap.has(sourceId)) {
        const parsed = parseShapeLabel(sourceInline[1]);
        nodeMap.set(sourceId, parsed);
      }

      // Extract inline node definitions from target side
      const targetInline = line.match(new RegExp(`${targetId}(\\[.*?\\]|\\(.*?\\)|\\{.*?\\})\\s*$`));
      if (targetInline && !nodeMap.has(targetId)) {
        const parsed = parseShapeLabel(targetInline[1]);
        nodeMap.set(targetId, parsed);
      }

      // Register bare nodes if not seen
      if (!nodeMap.has(sourceId)) {
        nodeMap.set(sourceId, { label: sourceId, type: 'service' });
      }
      if (!nodeMap.has(targetId)) {
        nodeMap.set(targetId, { label: targetId, type: 'service' });
      }

      connections.push({
        id: `${sourceId}-${targetId}`,
        sourceId,
        targetId,
        label: edgeLabel?.trim(),
      });
      continue;
    }

    // Try to parse as standalone node definition: A[Label]
    const nodeMatch = line.match(/^(\w+)(\[.*?\]|\(.*?\)|\{.*?\})\s*$/);
    if (nodeMatch) {
      const [, id, shape] = nodeMatch;
      if (!nodeMap.has(id)) {
        nodeMap.set(id, parseShapeLabel(shape));
      }
    }
  }

  // Auto-layout nodes
  const nodes = layoutNodes(nodeMap, connections, direction);

  return { nodes, connections, direction };
}

/**
 * Parse a shape wrapper like [Label], [(Label)], ((Label)), {Label}
 */
function parseShapeLabel(shape: string): { label: string; type: NodeType } {
  for (const { regex, type } of SHAPE_PATTERNS) {
    const match = shape.match(regex);
    if (match) {
      return { label: match[1], type };
    }
  }
  // Fallback: strip brackets
  const label = shape.replace(/[\[\](){}]/g, '').trim();
  return { label: label || 'Node', type: 'service' };
}

/**
 * Assign grid positions to nodes using BFS layering.
 */
function layoutNodes(
  nodeMap: Map<string, { label: string; type: NodeType }>,
  connections: CanvasConnection[],
  direction: 'TD' | 'LR'
): CanvasNode[] {
  if (nodeMap.size === 0) return [];

  const SPACING_X = 200;
  const SPACING_Y = 150;
  const OFFSET_X = 80;
  const OFFSET_Y = 60;

  // Build adjacency (children) and track incoming edges
  const children = new Map<string, string[]>();
  const incoming = new Map<string, number>();

  for (const id of nodeMap.keys()) {
    children.set(id, []);
    incoming.set(id, 0);
  }

  for (const conn of connections) {
    children.get(conn.sourceId)?.push(conn.targetId);
    incoming.set(conn.targetId, (incoming.get(conn.targetId) ?? 0) + 1);
  }

  // BFS from roots (nodes with no incoming edges)
  const roots = [...nodeMap.keys()].filter((id) => (incoming.get(id) ?? 0) === 0);
  if (roots.length === 0) {
    // Cycle — just use first node as root
    roots.push([...nodeMap.keys()][0]);
  }

  const layers = new Map<string, number>();
  const queue = [...roots];
  for (const r of roots) layers.set(r, 0);

  while (queue.length > 0) {
    const current = queue.shift()!;
    const currentLayer = layers.get(current) ?? 0;

    for (const child of children.get(current) ?? []) {
      if (!layers.has(child)) {
        layers.set(child, currentLayer + 1);
        queue.push(child);
      }
    }
  }

  // Assign any remaining nodes (disconnected) to layer 0
  for (const id of nodeMap.keys()) {
    if (!layers.has(id)) {
      layers.set(id, 0);
    }
  }

  // Group by layer
  const layerGroups = new Map<number, string[]>();
  for (const [id, layer] of layers) {
    if (!layerGroups.has(layer)) layerGroups.set(layer, []);
    layerGroups.get(layer)!.push(id);
  }

  // Assign positions
  const nodes: CanvasNode[] = [];
  for (const [layer, ids] of layerGroups) {
    ids.forEach((id, index) => {
      const info = nodeMap.get(id)!;
      const position =
        direction === 'TD'
          ? { x: OFFSET_X + index * SPACING_X, y: OFFSET_Y + layer * SPACING_Y }
          : { x: OFFSET_X + layer * SPACING_X, y: OFFSET_Y + index * SPACING_Y };

      nodes.push({ id, label: info.label, type: info.type, position });
    });
  }

  return nodes;
}
