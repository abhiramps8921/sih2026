import test from 'node:test';
import assert from 'node:assert/strict';
import {slhScore,templateSLH} from '../src/data.js';
test('SLH uses equal weights on a 100 point scale',()=>{
  assert.equal(slhScore({safety:4.5,legitimacy:4.8,hygiene:4.2}),90);
  assert.equal(slhScore({safety:5,legitimacy:5,hygiene:5}),100);
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
