'use strict';
// Validates today.json before the page sees it: known fields only, bounded plain strings.
// The page renders these as text, never HTML, so a tampered file can't run code.

const KINDS = new Set(['anchor', 'meal', 'meeting', 'event', 'buffer', 'reset', 'focus', 'break']);
const TEMPERS = new Set(['earned', 'angry', 'classic']);
const MOODS = new Set(['neutral', 'amused', 'serious', 'thoughtful', 'suspicious', 'surprised', 'happy', 'intimidating']);

const str = (v, max = 200) => (typeof v === 'string' ? v.slice(0, max) : '');
const hhmm = (v) => (typeof v === 'string' && /^([01]\d|2[0-3]):[0-5]\d$|^24:00$/.test(v) ? v : null);
const list = (v, n) => (Array.isArray(v) ? v.slice(0, n) : []);

function cleanFeed(raw) {
  if (!raw || raw.version !== 1 || !Array.isArray(raw.blocks)) throw new Error('not a Donna today.json (version 1)');
  return {
    date: /^\d{4}-\d{2}-\d{2}$/.test(raw.date) ? raw.date : '',
    generated_at: str(raw.generated_at, 40),
    mood: MOODS.has(raw.mood) ? raw.mood : '',
    temperament: TEMPERS.has(raw.temperament) ? raw.temperament : '',
    message: str(raw.message, 240),
    blocks: list(raw.blocks, 80)
      .map((b) => ({
        id: str(b.id, 24), start: hhmm(b.start), end: hhmm(b.end), kind: KINDS.has(b.kind) ? b.kind : 'event',
        title: str(b.title, 120), first_step: str(b.first_step, 160),
      }))
      .filter((b) => b.id && b.start && b.end && b.title),
    outfit: raw.outfit ? { summary: str(raw.outfit.summary, 160), why: str(raw.outfit.why, 160) } : null,
    occasions: list(raw.occasions, 5).map((o) => ({ who: str(o.who, 60), what: str(o.what, 60), action: str(o.action, 140) })),
    events: list(raw.events, 5).map((e) => ({ title: str(e.title, 100), when: str(e.when, 60), where: str(e.where, 80) })),
    wins: list(raw.wins, 3).map((w) => str(w, 140)).filter(Boolean),
    reminders: list(raw.reminders, 20).map((r) => ({ at: hhmm(r.at), text: str(r.text, 140) })).filter((r) => r.at && r.text),
  };
}

module.exports = { cleanFeed, str, hhmm, KINDS, MOODS, TEMPERS };
