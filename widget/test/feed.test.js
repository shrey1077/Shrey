'use strict';
// Run: npm test (no Electron needed)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { cleanFeed } = require('../feed');

const sample = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'sample', 'today.json'), 'utf8'));

test('the sample plan passes and keeps its blocks', () => {
  const feed = cleanFeed(sample);
  assert.strictEqual(feed.temperament, 'earned');
  assert.strictEqual(feed.blocks.length, sample.blocks.length);
  assert.strictEqual(feed.outfit.summary, sample.outfit.summary);
});

test('anything that is not a version 1 plan is refused', () => {
  assert.throws(() => cleanFeed({ blocks: [] }));
  assert.throws(() => cleanFeed({ version: 2, blocks: [] }));
  assert.throws(() => cleanFeed(null));
});

test('unknown fields are dropped and strings are bounded', () => {
  const feed = cleanFeed({
    version: 1, date: '2026-10-05', mood: 'furious', temperament: 'unhinged', message: 'x'.repeat(1000), script: '<img onerror=alert(1)>',
    blocks: [{ id: 'b1', start: '10:00', end: '10:45', kind: 'rm -rf', title: 'Deck', html: '<b>' }],
  });
  assert.strictEqual(feed.mood, '');
  assert.strictEqual(feed.temperament, '');
  assert.strictEqual(feed.message.length, 240);
  assert.strictEqual(feed.script, undefined);
  assert.strictEqual(feed.blocks[0].kind, 'event');
  assert.strictEqual(feed.blocks[0].html, undefined);
});

test('blocks with bad times or no title are dropped', () => {
  const feed = cleanFeed({
    version: 1, date: '2026-10-05',
    blocks: [
      { id: 'a', start: '25:00', end: '26:00', kind: 'focus', title: 'Bad time' },
      { id: 'b', start: '09:00', end: '09:30', kind: 'focus', title: '' },
      { id: 'c', start: '09:00', end: '09:30', kind: 'focus', title: 'Good' },
    ],
  });
  assert.deepStrictEqual(feed.blocks.map((b) => b.id), ['c']);
});

test('replies from Donna are kept as bounded text', () => {
  const feed = cleanFeed({ version: 1, date: '2026-10-05', blocks: [], replies: [{ at: '2026-10-05T09:00', text: 'Done. Moved it to 4 pm.' }, { at: 'x', text: '' }] });
  assert.deepStrictEqual(feed.replies, [{ at: '2026-10-05T09:00', text: 'Done. Moved it to 4 pm.' }]);
});
