// Lightweight deterministic layout: a force-directed simulation seeded on a
// circle. Keeps deps minimal (no dagre) while avoiding node overlap.

export interface LayoutInput {
  id: string;
}
export interface LayoutEdge {
  source: string;
  target: string;
}

export interface Positioned {
  [id: string]: { x: number; y: number };
}

export function forceLayout(
  nodes: LayoutInput[],
  edges: LayoutEdge[],
  opts: { width?: number; height?: number; iterations?: number } = {},
): Positioned {
  const width = opts.width ?? 900;
  const height = opts.height ?? 650;
  const iterations = opts.iterations ?? 320;
  const n = nodes.length;
  const pos: Positioned = {};
  if (n === 0) return pos;

  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(width, height) / 2.4;

  // Seed on a circle for a stable, deterministic start.
  nodes.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / n;
    pos[node.id] = {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    };
  });
  if (n === 1) return pos;

  const k = Math.sqrt((width * height) / n) * 0.9; // ideal distance
  const adjacency = new Set(edges.map((e) => `${e.source}->${e.target}`));
  const ids = nodes.map((node) => node.id);

  let temp = width / 8;
  const cool = temp / (iterations + 1);

  for (let iter = 0; iter < iterations; iter++) {
    const disp: Record<string, { x: number; y: number }> = {};
    for (const id of ids) disp[id] = { x: 0, y: 0 };

    // Repulsion between every pair.
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const a = pos[ids[i]];
        const b = pos[ids[j]];
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        let dist = Math.hypot(dx, dy) || 0.01;
        const force = (k * k) / dist;
        dx /= dist;
        dy /= dist;
        disp[ids[i]].x += dx * force;
        disp[ids[i]].y += dy * force;
        disp[ids[j]].x -= dx * force;
        disp[ids[j]].y -= dy * force;
      }
    }

    // Attraction along edges.
    for (const e of edges) {
      const a = pos[e.source];
      const b = pos[e.target];
      if (!a || !b) continue;
      let dx = a.x - b.x;
      let dy = a.y - b.y;
      const dist = Math.hypot(dx, dy) || 0.01;
      const force = (dist * dist) / k;
      dx = (dx / dist) * force;
      dy = (dy / dist) * force;
      disp[e.source].x -= dx;
      disp[e.source].y -= dy;
      disp[e.target].x += dx;
      disp[e.target].y += dy;
    }

    void adjacency;

    // Apply, limited by temperature, and keep within bounds.
    for (const id of ids) {
      const d = disp[id];
      const len = Math.hypot(d.x, d.y) || 0.01;
      pos[id].x += (d.x / len) * Math.min(len, temp);
      pos[id].y += (d.y / len) * Math.min(len, temp);
      pos[id].x = Math.max(20, Math.min(width - 20, pos[id].x));
      pos[id].y = Math.max(20, Math.min(height - 20, pos[id].y));
    }
    temp -= cool;
  }

  return pos;
}
