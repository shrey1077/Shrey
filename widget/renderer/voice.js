'use strict';
// Donna's voice for the widget: picks a line for the moment from Shrey's personality dials
// (0-10 each) and temperament. Pure and deterministic for a given seed, so it can be tested.
//
// Each situation has lines written in several traits. The dials weight which trait speaks;
// the temperament decides which traits are allowed at all. With `earned` (Shrey's choice), being
// late brings out sarcasm and anger, doing well brings out warmth and calm.

const Voice = (() => {
  const TRAITS = ['humour', 'sarcasm', 'anger', 'calm', 'happiness', 'sadness'];
  const DIALS = ['humour', 'sarcasm', 'anger', 'calm', 'happiness', 'sadness', 'chattiness'];
  const DEFAULT_DIALS = { humour: 6, sarcasm: 8, anger: 6, calm: 5, happiness: 7, sadness: 2, chattiness: 3 };
  const DIAL_HELP = {
    humour: 'Jokes and lightness',
    sarcasm: 'Dry, pointed remarks',
    anger: 'Bite and urgency',
    calm: 'Steady, unhurried',
    happiness: 'Warmth and praise',
    sadness: 'Lets disappointment show (never guilt)',
    chattiness: 'How much she says in chat',
  };

  // Which situation is late, good or neutral.
  const TONE = {
    lateFocus: 'late', lateMeeting: 'late', lateMeal: 'late', lateAnchor: 'late', lateStart: 'late', snooze: 'late',
    onTime: 'good', done: 'good', allDone: 'good', earnedBreak: 'good',
  };

  // {n} is minutes late.
  const BANK = {
    lateFocus: {
      sarcasm: ['Oh good, it started {n} minutes ago without you. Bold strategy.', '{n} minutes late. Riveting. The first step is right there.'],
      anger: ['{n} minutes late. Stop scrolling. Open it. Now.', 'It started {n} minutes ago. Move.'],
      humour: ['{n} minutes late. Even my coffee started on time.', "If lateness were a sport, you'd medal. {n} minutes. Go."],
      calm: ["It started {n} minutes ago. That's fine. Begin with the first step.", '{n} minutes in. No drama. Open it and start.'],
      sadness: ['It started {n} minutes ago. I had such hopes for this one.', '{n} minutes late. I set it up so nicely, too.'],
    },
    lateMeeting: {
      sarcasm: ["Your call started {n} minutes ago. I'm sure they love waiting.", '{n} minutes late to a meeting. Iconic.'],
      anger: ["They've waited {n} minutes. Join. Now."],
      humour: ['{n} minutes late. Blame the Wi-Fi, everyone does. Join.'],
      calm: ['The call started {n} minutes ago. Join now and apologise once.'],
      sadness: ["They've been waiting {n} minutes. A little embarrassing for both of us."],
    },
    lateMeal: {
      sarcasm: ["Food was due {n} minutes ago. 'One more thing' is not a food group."],
      anger: ['{n} minutes past mealtime. Eat. Now.'],
      humour: ['{n} minutes late for food. Your stomach has filed a formal complaint.'],
      calm: ['Mealtime was {n} minutes ago. Step away and eat something real.'],
      sadness: ['Skipping food again. That makes me sad. Go and eat.'],
    },
    lateAnchor: {
      sarcasm: ["{n} minutes past. The day won't start itself. Shocking, I know."],
      anger: ['{n} minutes behind. Up. Now.'],
      humour: ['{n} minutes late. The day is waiting, tapping its foot.'],
      calm: ['{n} minutes behind. Small step: just this one.'],
      sadness: ["{n} minutes behind already. Let's not make it a habit."],
    },
    lateStart: {
      sarcasm: ['Ah, you made it. Only {n} minutes late.', 'Finally. So kind of you to join.'],
      anger: ["{n} minutes late. Go, and don't stop."],
      humour: ['And the late arrival of the day goes to... you. Go.'],
      calm: ["You've started. That's what matters."],
      sadness: ["Late, but here. I'll take it."],
    },
    snooze: {
      sarcasm: ['Five more minutes. Of course. I have nowhere to be either.', "Snoozed. Again. I'm counting, out loud."],
      anger: ['Five minutes. Not six.'],
      humour: ['Snooze accepted. Your future self sends regards.'],
      calm: ['Five minutes. Then we start.'],
      sadness: ["Five more minutes. I'll wait."],
    },
    onTime: {
      happiness: ['Right on time. I noticed. That was lovely.', "You started exactly when you said you would. I'm proud of you."],
      calm: ['On time. Steady. Exactly like that.'],
      humour: ['On time? Should I alert the press? Lovely work.'],
      anger: ["Good. That's how it's done."],
      sarcasm: ['Punctual. Who are you, and can you stay?'],
    },
    done: {
      happiness: ['Done, and done well. Take a breath.', "That's one more finished. You're doing so well."],
      calm: ['Done. Breathe. On to the next, gently.'],
      humour: ['Done already. Quick, before anyone notices how good you are.'],
      anger: ["Fine. That was genuinely good. Don't make me say it twice."],
      sarcasm: ["Finished. I'll alert the historians."],
    },
    allDone: {
      happiness: ["Everything done today. I'm genuinely proud of you. Rest now."],
      calm: ["All done. Close the laptop. You've earned the evening."],
      humour: ["Everything done. I'm almost out of things to nag about."],
      anger: ["All done. Fine. I'm impressed. Don't tell anyone."],
      sarcasm: ['All done. Unprecedented. Take the evening.'],
    },
    earnedBreak: {
      happiness: ["Rest properly. You've earned this one.", 'Lovely work. Water, a stretch, one slow breath.'],
      calm: ['Break. Breathe. Nothing else for ten minutes.'],
      humour: ["Break time. The work isn't going anywhere. Sadly."],
      anger: ['Break. Actual break. Away from the screen.'],
      sarcasm: ['A break you earned. Look at you.'],
    },
    focus: {
      calm: ['One thing. This thing.', 'Just the next small step.'],
      anger: ['Phone face down. I mean it.'],
      humour: ["Focus mode. I'll guard the door with a stapler."],
      sarcasm: ['Focus. I know, revolutionary.'],
      happiness: ["You've got this one."],
    },
    meeting: {
      calm: ['Notes open. Be on time.'],
      anger: ['Be on time. Be brilliant. In that order.'],
      humour: ['Camera on. Smile like you read the agenda.'],
      sarcasm: ['A meeting. Thrilling. Be on time anyway.'],
      happiness: ["You'll do great. Notes open?"],
    },
    break: {
      calm: ['Break. Away from the screen.'],
      anger: ['Break means away from the screen. Including the phone.'],
      humour: ["Break time. Stare at a wall. It's very relaxing."],
      sarcasm: ["A break. Not a scroll. There's a difference."],
      happiness: ['Stretch, water, a little sunshine.'],
    },
    meal: {
      calm: ['Food. Real food.'],
      anger: ['Eat. Not after one more thing. Now.'],
      humour: ['Mealtime. Coffee is not a food group.'],
      sarcasm: ["Food. You've heard of it."],
      happiness: ['Time to eat something good.'],
    },
    anchor: {
      calm: ['Do this one properly.'],
      anger: ['Do it now. Then we talk.'],
      humour: ['Small step, big day.'],
      sarcasm: ['This one counts too, believe it or not.'],
      happiness: ['A good start makes a good day.'],
    },
    buffer: {
      calm: ['Get ready. Notes open, water poured.'],
      anger: ['Get ready. Not in five minutes. Now.'],
      humour: ['Two minutes to look like you prepared.'],
      sarcasm: ['Prep time. Wild concept.'],
      happiness: ["Take a breath. You'll be great."],
    },
    event: {
      calm: ['Leave on time.'],
      anger: ["Don't be late."],
      humour: ['Have fun. Responsibly-ish.'],
      sarcasm: ['Try to arrive before it ends.'],
      happiness: ['Enjoy it. You deserve it.'],
    },
    idle: {
      calm: ['Nothing scheduled. Use it on purpose.'],
      anger: ['Nothing scheduled. Suspicious.'],
      humour: ["Free time. Don't let it wander off."],
      sarcasm: ["An empty slot. Let's not waste it, shall we."],
      happiness: ['A little free time. Lovely.'],
    },
    none: {
      calm: ['No plan yet. Ask me to plan your day.'],
      anger: ['No plan. Ask me. Now.'],
      humour: ['No plan. Bold. Ask me for one.'],
      sarcasm: ['No plan. Living dangerously, I see.'],
      happiness: ["Let's plan your day together."],
    },
    stale: {
      calm: ["That plan is old. Ask me for today's."],
      anger: ['Old plan. Get a new one.'],
      humour: ["That plan is vintage. Ask for today's."],
      sarcasm: ["Yesterday's plan. Very retro."],
      happiness: ["New day. Let's make a fresh plan."],
    },
    skip: {
      calm: ['Skipped. Fine. The next one counts.'],
      anger: ["Skipped. The next one doesn't get skipped."],
      humour: ["Skipped. We'll pretend that didn't happen."],
      sarcasm: ['Skipped. Shocking.'],
      sadness: ['Skipped. Oh well. Next one.'],
      happiness: ['No problem. On to the next.'],
    },
    noted: {
      calm: ['Noted. Back to what you were doing.'],
      anger: ['Noted. Now back to work.'],
      humour: ["Noted. Filed under things I'll remember for you."],
      sarcasm: ["Noted. Another thing I'll remember for you."],
      happiness: ["Got it. I'll take care of it."],
    },
    chatAck: {
      calm: ["Noted. I'll answer at my next check-in."],
      anger: ["Got it. I'll deal with it at my next check-in."],
      humour: ["Message received. I'll reply at my next check-in, like a very organised pigeon."],
      sarcasm: ["Noted. I'll reply at my next check-in. Try to contain your excitement."],
      happiness: ["Got it. I'll get back to you at my next check-in."],
    },
  };

  const TRAIT_FACE = { sarcasm: 'amused', anger: 'angry', humour: 'amused', calm: 'serious', sadness: 'thoughtful', happiness: 'happy' };

  const hash = (s) => [...String(s)].reduce((a, c) => (Math.imul(a, 31) + c.charCodeAt(0)) >>> 0, 2166136261);

  function clampDials(d) {
    const out = {};
    for (const k of DIALS) {
      const v = Number(d && d[k]);
      out[k] = Number.isFinite(v) ? Math.max(0, Math.min(10, Math.round(v))) : DEFAULT_DIALS[k];
    }
    return out;
  }

  // How much each trait may speak, by temperament and tone.
  function weights(situation, dials, temperament) {
    const tone = TONE[situation] || 'neutral';
    const d = clampDials(dials);
    const factor = { humour: 1, sarcasm: 1, anger: 1, calm: 1, happiness: 1, sadness: 1 };
    if (temperament === 'classic') {
      factor.anger = 0;
      factor.sarcasm = 0;
    } else if (temperament === 'angry') {
      factor.anger = 1.5;
      factor.sarcasm = 1.2;
      factor.happiness = 0.3;
    } else {
      // earned: sarcasm and anger only when late; warmth only when doing well.
      if (tone === 'good') {
        factor.anger = 0;
        factor.sarcasm = 0;
        factor.sadness = 0;
      } else if (tone === 'late') {
        factor.happiness = 0;
      } else {
        factor.anger = 0.5;
        factor.sarcasm = 0.5;
      }
    }
    const w = {};
    for (const t of TRAITS) w[t] = (d[t] / 10) ** 2 * factor[t];
    return w;
  }

  function line(situation, opts = {}) {
    const bank = BANK[situation] || BANK.idle;
    const w = weights(situation, opts.dials, opts.temperament || 'earned');
    const options = Object.keys(bank).filter((t) => w[t] > 0);
    const total = options.reduce((s, t) => s + w[t], 0);
    let trait;
    if (!total) {
      trait = bank.calm ? 'calm' : bank.happiness ? 'happiness' : Object.keys(bank)[0];
    } else {
      let r = (hash(`${opts.seed || ''}|${situation}`) % 10000) / 10000 * total;
      trait = options[options.length - 1];
      for (const t of options) {
        r -= w[t];
        if (r < 0) {
          trait = t;
          break;
        }
      }
    }
    const lines = bank[trait];
    const text = lines[hash(`${opts.seed || ''}|${trait}`) % lines.length].replace(/\{n\}/g, String(opts.n || 0));
    return { text, trait, face: TRAIT_FACE[trait] || 'neutral' };
  }

  // The widget chat's instructions to Donna, from the dials. Only letters, digits and plain
  // punctuation, so it is safe to pass on a command line.
  function chatBrief(dials, temperament) {
    const d = clampDials(dials);
    const length = d.chattiness <= 3 ? 'at most three short sentences' : d.chattiness <= 6 ? 'one short paragraph' : 'whatever it takes, under 120 words';
    const parts = TRAITS.map((t) => `${t} ${d[t]}`).join(', ');
    return `Shrey is writing from the desktop widget chat. Temperament: ${temperament}. Personality dials set by Shrey, 0 to 10: ${parts}. `
      + `Let the dials set your tone, within the hard limits in your manual. The chat window is small: reply in ${length}. `
      + 'You cannot get tool approvals here, so for anything that sends, posts, books or changes a calendar, prepare it and ask Shrey to confirm in the Claude app.';
  }

  return { TRAITS, DIALS, DEFAULT_DIALS, DIAL_HELP, BANK, TONE, line, weights, clampDials, chatBrief };
})();

if (typeof module !== 'undefined') module.exports = Voice;
