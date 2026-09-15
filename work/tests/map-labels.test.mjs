import test from 'node:test';
import assert from 'node:assert/strict';
import { spreadMapLabels } from '../src/map-labels.js';

test('all sixteen nearby stop labels remain separate in itinerary order', () => {
  const points = Array.from({ length: 16 }, (_, index) => ({ x: 100 + index % 2, y: 100 }));
  const labels = spreadMapLabels(points);
  assert.equal(labels.length, 16);
  assert.deepEqual(labels[0], points[0]);
  labels.forEach((label, index) => {
    labels.slice(index + 1).forEach((other) => {
      assert.ok(Math.hypot(label.x - other.x, label.y - other.y) >= 38);
    });
  });
});

test('isolated markers keep their geographic positions', () => {
  const points = [{ x: 0, y: 0 }, { x: 100, y: 100 }];
  assert.deepEqual(spreadMapLabels(points), points);
});
