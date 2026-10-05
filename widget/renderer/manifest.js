'use strict';
// Where each emotion and scene sits on Donna's art sheets, and which picture to show when.
//
// Rectangles are [x, y, width, height] on a 1536x1024 sheet (scaled to the real size). The cutter
// snaps each edge to the white gutter between panels, so these only need to be close. Slots:
//   body.<emotion>  full or three-quarter figure      face.<emotion>  close-up
//   scene.<moment>  Donna doing something             bust            half-bust portrait
// A slot can hold several pictures; the widget rotates through them for variety.

const Manifest = (() => {
  const SHEETS = {
    smiles: {
      label: 'Smiles (normal smile to enchanted)',
      cuts: [
        ['body.normal', [168, 64, 264, 664]], ['body.happy', [443, 64, 283, 664]], ['body.laughing', [737, 64, 271, 664]],
        ['body.playful', [1019, 64, 264, 664]], ['body.adoring', [1293, 64, 243, 664]],
        ['face.normal', [2, 737, 299, 285]], ['face.happy', [313, 737, 297, 285]], ['face.laughing', [622, 737, 294, 285]],
        ['face.playful', [927, 737, 296, 285]], ['face.adoring', [1235, 737, 299, 285]],
      ],
    },
    poses: {
      label: 'Poses (over the shoulder, walking, desk, phone, coffee)',
      cuts: [
        ['bust', [2, 2, 564, 1020]], ['body.normal', [574, 2, 300, 1020]], ['scene.focus', [882, 2, 388, 416]],
        ['face.thoughtful', [1278, 2, 256, 416]], ['scene.call', [882, 427, 199, 259]], ['face.happy', [1090, 427, 215, 259]],
        ['face.amused', [1314, 427, 220, 259]], ['scene.coffee', [882, 694, 224, 328]], ['face.relaxed', [1114, 694, 191, 328]],
        ['scene.reading', [1314, 694, 220, 328]],
      ],
    },
    day: {
      label: 'A day in her life (morning to winding down)',
      cuts: [
        ['scene.morning', [2, 50, 239, 498]], ['scene.ready', [250, 50, 193, 498]], ['scene.commute', [454, 50, 208, 498]],
        ['scene.focus', [672, 50, 241, 498]], ['scene.lunch', [923, 50, 200, 498]], ['scene.exercise', [1132, 50, 197, 498]],
        ['scene.winddown', [1339, 50, 195, 498]], ['bust', [150, 560, 295, 462]],
      ],
    },
    bodyEmotions: {
      label: 'Full-body emotions (serious, angry, amused, happy, thoughtful)',
      cuts: [
        ['body.serious', [150, 76, 276, 946]], ['body.angry', [437, 76, 253, 946]], ['body.amused', [701, 76, 265, 946]],
        ['body.happy', [978, 76, 280, 946]], ['body.thoughtful', [1269, 76, 265, 946]],
      ],
    },
    intense: {
      label: 'Intense emotions (cold anger, fury, crying, cooling down)',
      cuts: [
        ['body.angry', [2, 70, 339, 548]], ['body.furious', [352, 70, 334, 548]], ['body.crying', [697, 70, 289, 548]],
        ['body.sobbing', [996, 70, 280, 548]], ['body.cooling', [1286, 70, 248, 548]],
        ['face.angry', [2, 627, 339, 296]], ['face.furious', [350, 627, 324, 296]], ['face.crying', [686, 627, 288, 296]],
        ['face.sobbing', [985, 627, 249, 296]], ['face.cooling', [1245, 627, 289, 296]],
      ],
    },
    event: {
      label: 'Gig night (an evening event)',
      cuts: [
        ['scene.event', [100, 2, 360, 1020]], ['face.relaxed', [874, 2, 317, 523]], ['scene.celebrate', [1199, 2, 335, 523]],
        ['scene.chill', [472, 533, 232, 489]], ['face.cool', [952, 533, 239, 489]], ['face.blissful', [1199, 533, 335, 489]],
      ],
    },
    office: {
      label: 'Office emotions (normal, happy, amused, surprised, thoughtful)',
      cuts: [
        ['body.normal', [150, 76, 276, 946]], ['body.happy', [437, 76, 251, 946]], ['body.amused', [699, 76, 267, 946]],
        ['body.surprised', [977, 76, 259, 946]], ['body.thoughtful', [1246, 76, 288, 946]],
      ],
    },
    character: {
      label: 'Character sheet (turnaround, in action, expressions)',
      cuts: [
        ['body.normal', [472, 32, 124, 466], { key: 'paper' }], ['scene.focus', [833, 50, 173, 447]],
        ['scene.reading', [1009, 0, 176, 497]], ['scene.call', [1188, 0, 172, 497]], ['scene.coffee', [1362, 0, 174, 497]],
        ['bust', [150, 90, 316, 610]],
        // The EXPRESSIONS row; the widget also finds these panels by itself.
        ['face.normal', [478, 546, 120, 148]], ['face.amused', [606, 546, 117, 148]], ['face.serious', [730, 546, 120, 148]],
        ['face.thoughtful', [858, 546, 120, 148]], ['face.suspicious', [985, 546, 124, 148]], ['face.surprised', [1116, 546, 120, 148]],
        ['face.happy', [1243, 546, 123, 148]], ['face.angry', [1374, 546, 147, 148]],
      ],
    },
  };

  // Filename hints for guessing which sheet a file is.
  const GUESS = [
    [/smile|laugh|enchant|adore|love/i, 'smiles'],
    [/day|life|routine|morning|pickle/i, 'day'],
    [/cry|furious|intense|rage|tears/i, 'intense'],
    [/rasta|gig|event|concert|festival|party/i, 'event'],
    [/office/i, 'office'],
    [/emotion|angry|mood/i, 'bodyEmotions'],
    [/pose|candid|casual/i, 'poses'],
    [/character|sheet|turnaround|reference/i, 'character'],
  ];

  // When a picture is missing, the next one in line stands in.
  const FALLBACK = {
    furious: ['angry', 'serious'], angry: ['serious', 'suspicious'], sobbing: ['crying', 'sad', 'thoughtful'],
    crying: ['sad', 'thoughtful'], sad: ['thoughtful'], cooling: ['thoughtful', 'serious'],
    adoring: ['playful', 'happy'], laughing: ['happy'], playful: ['amused', 'happy'], amused: ['playful', 'happy'],
    relaxed: ['happy'], blissful: ['relaxed', 'happy'], cool: ['amused', 'normal'], suspicious: ['serious'],
    surprised: ['normal'], thoughtful: ['serious'], serious: ['normal'], happy: ['normal'],
  };

  function chain(emotion) {
    const out = [emotion];
    for (let i = 0; i < out.length; i += 1) for (const f of FALLBACK[out[i]] || []) if (!out.includes(f)) out.push(f);
    if (!out.includes('normal')) out.push('normal');
    return out;
  }

  // The scene for a block in the plan, from its kind, title and time.
  function sceneFor(block) {
    const t = (block.title || '').toLowerCase();
    const start = Number((block.start || '00:00').slice(0, 2));
    if (/pickle|gym|run|walk|yoga|workout|exercise|swim|cricket|football|badminton/.test(t)) return 'exercise';
    if (/wake|morning/.test(t)) return 'morning';
    if (/wind|sleep|bed|night/.test(t)) return 'winddown';
    if (/shower|get ready|getting ready|dress/.test(t)) return 'ready';
    if (/commute|leave|drive|travel|cab|metro/.test(t)) return 'commute';
    if (/gig|concert|music|festival|party|show/.test(t)) return 'event';
    switch (block.kind) {
      case 'focus': return 'focus';
      case 'meeting': return 'call';
      case 'buffer': return 'reading';
      case 'break': return 'coffee';
      case 'meal': return start < 10 ? 'morning' : 'lunch';
      case 'anchor': return start < 9 ? 'morning' : start >= 21 ? 'winddown' : '';
      case 'event': return 'event';
      default: return '';
    }
  }

  // Which sheet a file probably is, from its name.
  function guess(filename) {
    const hit = GUESS.find(([re]) => re.test(filename));
    return hit ? hit[1] : '';
  }

  const SLOT_RE = /^(body|face|scene)\.[a-z]+$|^bust$/;

  return { SHEETS, chain, sceneFor, guess, SLOT_RE };
})();

if (typeof module !== 'undefined') module.exports = Manifest;
