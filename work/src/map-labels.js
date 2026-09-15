// Positions are screen pixels so labels stay readable at every zoom level.
export function spreadMapLabels(points, spacing = 38) {
  const placed = [];
  return points.map((point) => {
    let candidate = point;
    for (
      let attempt = 0;
      placed.some((other) => Math.hypot(candidate.x - other.x, candidate.y - other.y) < spacing);
      attempt += 1
    ) {
      const ring = Math.floor(attempt / 12) + 1;
      const angle = ((attempt % 12) * Math.PI) / 6;
      candidate = {
        x: point.x + Math.cos(angle) * spacing * ring,
        y: point.y + Math.sin(angle) * spacing * ring,
      };
    }
    placed.push(candidate);
    return candidate;
  });
}
