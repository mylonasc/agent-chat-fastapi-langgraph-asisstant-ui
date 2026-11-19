export interface GraphNode {
  id: string;
  label?: string;
  weight?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  label?: string;
  weight?: number;
}

export interface GraphData {
  directed: boolean;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphControlsState {
  charge: number;
  linkDistance: number;
  showLabels: boolean;
  nodeScale: number;
  edgeScale: number;
}
