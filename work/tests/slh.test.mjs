import test from 'node:test';
import assert from 'node:assert/strict';
import {slhScore,templateSLH} from '../src/data.js';
test('SLH uses equal weights on a 100 point scale',()=>{
  assert.equal(slhScore({safety:4.5,legitimacy:4.8,hygiene:4.2}),90);
  assert.equal(slhScore({safety:5,legitimacy:5,hygiene:5}),100);
});
test('Itinerary metadata distinguishes community and mixed sources', () => {
  const demo = {id:'a', slh:{safety:4,legitimacy:4,hygiene:4,reviews:20,source:'demo',reviewed_at:'2026-09-01'}};
  const community = {id:'b',slh:{safety:2,legitimacy:2,hygiene:2,reviews:3,source:'community',reviewed_at:'2026-09-15'}};
  const mixed = templateSLH({stops:['a','b']}, [demo,community]);
  assert.equal(mixed.source, 'mixed');
  assert.equal(mixed.reviewed_at, '2026-09-15');
  assert.equal(slhScore(mixed), 60);
  assert.equal(templateSLH({stops:['b']}, [community]).source, 'community');
});
test('Missing dimensions are unrated, not zero or inflated',()=>{
  assert.equal(slhScore(null),null);
  assert.equal(slhScore({safety:4.5,legitimacy:4.8}),null);
});
test('Out-of-range values cannot fabricate a score',()=>{
  assert.equal(slhScore({safety:9,legitimacy:4,hygiene:4}),null);
});
test('Trip scores are computed from actual stop dimensions',()=>{
  const rating=templateSLH({stops:['a','b']},[{id:'a',slh:{safety:4,legitimacy:4,hygiene:4,reviews:1}},{id:'b',slh:{safety:5,legitimacy:5,hygiene:5,reviews:2}}]);
  assert.equal(slhScore(rating),90);
  assert.equal(rating.reviews,3);
  assert.equal(templateSLH({stops:['missing']},[]),null);
});
