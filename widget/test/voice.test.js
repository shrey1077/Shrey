'use strict';
const test = require('node:test');
const assert = require('node:assert');
const Voice = require('../renderer/voice');
const Manifest = require('../renderer/manifest');

const traitsSeen = (situation, opts, runs = 200) => {
  const seen = new Set();
  for (let i = 0; i < runs; i += 1) seen.add(Voice.line(situation, { ...opts, seed: `s${i}` }).trait);
  return seen;
};

test('earned: late is never sweet, doing well is never angry or sarcastic', () => {
  const dials = { humour: 10, sarcasm: 10, anger: 10, calm: 10, happiness: 10, sadness: 10 };
  const late = traitsSeen('lateFocus', { dials, temperament: 'earned', n: 9 });
  assert.ok(!late.has('happiness'));
  assert.ok(late.has('sarcasm') && late.has('anger'));
  const good = traitsSeen('done', { dials, temperament: 'earned' });
  assert.ok(!good.has('anger') && !good.has('sarcasm'));
  assert.ok(good.has('happiness'));
});

test('classic never uses anger or sarcasm', () => {
  const dials = { humour: 0, sarcasm: 10, anger: 10, calm: 2, happiness: 2, sadness: 0 };
  const seen = traitsSeen('lateMeeting', { dials, temperament: 'classic', n: 5 });
  assert.ok(!seen.has('anger') && !seen.has('sarcasm'));
});

test('a dial at zero silences that trait; minutes fill in', () => {
  const dials = { humour: 0, sarcasm: 10, anger: 0, calm: 0, happiness: 0, sadness: 0 };
  const said = Voice.line('lateFocus', { dials, temperament: 'earned', n: 12, seed: 'x' });
  assert.strictEqual(said.trait, 'sarcasm');
  assert.match(said.text, /12/);
  assert.doesNotMatch(said.text, /\{n\}/);
});

test('every situation has lines and dials are clamped', () => {
  for (const [key, bank] of Object.entries(Voice.BANK)) {
    assert.ok(Object.keys(bank).length >= 3, key);
    assert.ok(Voice.line(key, { seed: 'a' }).text.length > 0, key);
  }
  assert.deepStrictEqual(Voice.clampDials({ humour: 99, sarcasm: -3, anger: 'x' }).humour, 10);
  assert.strictEqual(Voice.clampDials({ sarcasm: -3 }).sarcasm, 0);
});

test('the chat brief is safe to put on a command line', () => {
  const brief = Voice.chatBrief(Voice.DEFAULT_DIALS, 'earned');
  assert.match(brief, /^[A-Za-z0-9 ,.:;()'*/_=-]*$/);
  assert.match(brief, /sarcasm 8/);
});

test('every cut sits on the sheet and names a valid slot', () => {
  for (const [name, sheet] of Object.entries(Manifest.SHEETS)) {
    for (const [slot, [x, y, w, h]] of sheet.cuts) {
      assert.ok(Manifest.SLOT_RE.test(slot), `${name}: ${slot}`);
      assert.ok(x >= 0 && y >= 0 && w > 40 && h > 40 && x + w <= 1536 && y + h <= 1024, `${name}: ${slot}`);
    }
  }
});

test('scenes follow the plan, and missing emotions fall back sensibly', () => {
  assert.strictEqual(Manifest.sceneFor({ kind: 'meal', title: 'Lunch', start: '13:15' }), 'lunch');
  assert.strictEqual(Manifest.sceneFor({ kind: 'event', title: 'Evening pickleball', start: '18:00' }), 'exercise');
  assert.strictEqual(Manifest.sceneFor({ kind: 'anchor', title: 'Wind down', start: '22:00' }), 'winddown');
  assert.strictEqual(Manifest.sceneFor({ kind: 'meeting', title: 'Call with Priya', start: '11:00' }), 'call');
  assert.deepStrictEqual(Manifest.chain('sobbing').slice(0, 3), ['sobbing', 'crying', 'sad']);
  assert.strictEqual(Manifest.chain('furious').at(-1), 'normal');
  assert.strictEqual(Manifest.guess('Donna smiles sheet.png'), 'smiles');
  assert.strictEqual(Manifest.guess('crying and furious.png'), 'intense');
});
