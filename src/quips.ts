import { babble } from './audio';

export type Speaker = 'cab' | 'techbro' | 'cmo' | 'ceo' | 'founder' | 'sweater' | 'rocket' | 'safety';
export type QuipEvent =
  | 'pickup' | 'dropoff' | 'walkout' | 'idle'
  | 'jump' | 'jumpFirst' | 'nearMiss' | 'crash' | 'drift' | 'slow' | 'timeLow'
  | 'fired' | 'back' | 'reroute' | 'safetyLow'
  | 'dash' | 'smash' | 'geyser' | 'underwater' | 'bigAir';

export const SPEAKERS: Record<Speaker, { name: string; color: string; pitch: number }> = {
  cab: { name: 'YOUR CAB', color: '#14a892', pitch: 880 },
  techbro: { name: 'TECH BRO', color: '#2f6fd6', pitch: 300 },
  cmo: { name: 'ABG CMO', color: '#e0458f', pitch: 620 },
  ceo: { name: 'PSYCHO CEO', color: '#d6332b', pitch: 220 },
  founder: { name: 'THE FOUNDER', color: '#e07b1a', pitch: 420 },
  sweater: { name: 'THE SWEATER', color: '#6b6f76', pitch: 360 },
  rocket: { name: 'THE ROCKET GUY', color: '#222222', pitch: 260 },
  safety: { name: 'THE SAFETY GUY', color: '#c86f3c', pitch: 400 },
};

// Edit freely: lines are picked from a shuffled bag, so every line plays
// once before any repeats. "{dest}" is replaced with a place name.
export const LINES: Record<Speaker, Partial<Record<QuipEvent, string[]>>> = {
  cab: {
    pickup: ['Welcome aboard. Please buckle up. I will not.', "Hello! I'm legally a very careful driver.", 'Your safety is my top priority. Hold on.'],
    crash: ["I'm sorry. I'm so sorry. Rerouting.", 'That object was not in my training data.', 'Filing incident report... deleting incident report.', 'Minor contact event. Nobody saw that.'],
    jump: ['Unexpected elevation change. Enjoy!', 'Wheels are optional, per my latest update.', 'I am briefly an aircraft.'],
    nearMiss: ['Within tolerance.', 'Gap detected. Gap taken.'],
    safetyLow: ['My permit is under review.', 'The DMV has entered the chat.', "Please don't tell the regulators."],
    dropoff: ['Thank you for riding. Please rate me five stars. Or else.', 'Arrived. Your data has been lovingly retained.'],
    walkout: ['Rating lowered. Feelings: none.', 'Another satisfied customer. Statistically.'],
    idle: ['Lidar spinning. Vibes immaculate.', 'I can see in 360 degrees. I choose not to.', 'Updating terms of service... done.'],
    dash: ['Engaging ludicrous mode.', 'Acceleration profile: unhinged.'],
    smash: ['Street furniture reclassified as projectiles.', 'That was in the way. It is no longer in the way.', 'Cone detected. Cone ignored.'],
    geyser: ['Water feature unlocked.', 'I have created a fountain. You are welcome.'],
    underwater: ['I am now a submarine. Please remain seated.', 'Waterproofing: untested. Now tested.', 'Recalculating route via the ocean floor.'],
    bigAir: ['Altitude exceeds my operating permit.', 'Requesting clearance from air traffic control.', 'I can see my depot from here.'],
  },
  techbro: {
    pickup: ["Bro. Let's GO. I've got a pitch in ten.", 'Yo, is this the robot one? Sick. Very on thesis.', "Quick ride, bro, I'm between two coffee chats."],
    jump: ['LET\'S GOOO, this is going on my Strava.', 'Bro we are LITERALLY flying. 10x.', "That's a hockey stick, bro."],
    nearMiss: ['Bro! Move fast and miss things!', 'Disruption, baby!'],
    crash: ['Bro, my cold brew!', "That's fine, that's a learning.", "We'll call that a pivot."],
    drift: ['Sideways like my cap table, bro.', 'Drift mode. Love the UX.'],
    slow: ['Bro this ride has no product-market fit.', 'Are we waiting on legal or what?'],
    timeLow: ["Bro I'm gonna miss the pitch!", 'Bro. BRO. Hurry.'],
    dropoff: ["You're cracked, bro. Let's grab coffee sometime. We won't.", "Huge. I'll put you in the deck."],
    walkout: ["I'm just gonna scooter it, bro."],
    idle: ["So I'm building an AI for dogs. But B2B.", 'I do cold plunges, so this ride is nothing.', 'My sleep ring says my stress is top one percent.', "We're pre-revenue but post-vibes."],
  },
  cmo: {
    pickup: ['Hiii, okay, can you find my good angle?', 'Oh my god, a robot. So on brand.', 'Hey! I need to be at my thing, like, now.'],
    jumpFirst: ["Wait, do that again, I wasn't filming.", 'Nooo, my phone was locked. Again!'],
    jump: ["Okay THAT's the content!", "Posting that. Tagging you. What's your handle?", 'Engagement is going to be insane.'],
    nearMiss: ['That was so close, I love that for us.', 'Okay, chaos. Very authentic.'],
    crash: ['My lash extensions!', "Okay, we're cutting that part.", 'Not the vibe. Not the vibe.'],
    drift: ['The drift? Iconic.', 'This is giving Tokyo.'],
    slow: ['This is so not giving speed.', 'Can we be more... viral?'],
    timeLow: ["I'm going to be SO late to my own launch.", 'Hurry, my matcha is dying.'],
    dropoff: ["Thank youuu! I'll tag you!", 'Five stars. The content was elite.'],
    walkout: ['Ugh. Calling a different robot.'],
    idle: ["Our brand voice is basically 'unbothered.'", 'I rebranded my dog this morning.', "We're a lifestyle brand. For B2B SaaS."],
  },
  ceo: {
    pickup: ["Drive. Now. You're already behind.", 'Go! Time is equity!', "Don't talk. Drive."],
    jump: ['GOOD. MORE.', "That's the hustle I want to see!"],
    nearMiss: ['Closer! CLOSER!', "That's what we call bias for action!"],
    crash: ["You're FIRED. Keep driving.", 'Unacceptable! Do it again, but faster!', "I'm taking that out of your compute."],
    drift: ['Sideways is still forward!'],
    slow: ['WHY ARE WE SLOW?', 'Is this a four-day work week? IS IT?', "I've fired people for slower than this!"],
    timeLow: ['You have five seconds to justify your existence!', 'Faster, or I replace you with a slightly worse robot!'],
    dropoff: ["Adequate. You're promoted to unpaid.", 'Fine. Expect my feedback at 3 a.m.'],
    walkout: ["I'm walking. I'm faster than you anyway."],
    idle: ['I laid off my hobbies to focus.', 'Sleep is a growth constraint.', "I told the board I'd 10x. I meant it violently."],
  },
  founder: {
    pickup: ["Hey! I can't pay cash, but how do you feel about equity?", 'Hi! Quick ride, super capital-efficient please.'],
    jump: ['Here, have some shares!', 'Love it. Vesting immediately!'],
    nearMiss: ["Bonus shares! They're worth... something!"],
    crash: ["That's a down round.", 'Our runway just got shorter.'],
    drift: ["We're iterating!"],
    slow: ["We're burning runway here.", 'Every second costs us valuation.'],
    timeLow: ["We're about to default on this ride!"],
    dropoff: ["Here's your equity! Four-year vest, one-year cliff.", "You're basically an early employee now."],
    walkout: ['Pivoting to walking.'],
    idle: ["We're Uber, but for Ubers.", 'Our valuation is a vibe.', 'I sold my car to fund the seed round. Hence this.'],
  },
  sweater: {
    pickup: ['hey. so excited about this ride.', 'hi. this might be the most important ride in history.'],
    jump: ['this is fine. we have a plan for this.', 'feel the agi.'],
    nearMiss: ['we take that very seriously.', 'iterative deployment.'],
    crash: ["we'll need a lot more compute to fix that.", 'lessons learned. moving on.'],
    drift: ['feels like a step change.'],
    slow: ['we could go faster with seven trillion dollars.', 'intelligence too cheap to meter. unlike this fare.'],
    timeLow: ['no rush. but also, rush.'],
    fired: ["oh. i've been fired. i love the board.", 'going to spend some time with my family.'],
    back: ["anyway, i'm back.", "update: i'm back. fare's doubled."],
    dropoff: ['thanks. that was a big ride for humanity.', 'great ride. agi next year, probably.'],
    walkout: ["i'll just build my own car."],
    idle: ["we're a small nonprofit. mostly.", "i don't really think about money.", 'can i interest you in a scan of your eyeball?'],
  },
  rocket: {
    pickup: ["Take me to Mars. Or Fremont, whichever's closer.", 'This car will be fully self-driving next year.', 'Interesting.'],
    jump: ['Rapid unscheduled airtime. Nominal.', 'Excellent. Excellent.'],
    nearMiss: ['Wow.', 'Haha. True.'],
    crash: ['Concerning.', 'Looking into this.', "That didn't happen."],
    drift: ['!!'],
    slow: ["Full self-driving next year. You're the proof.", 'This car is woke.'],
    timeLow: ['Hardcore mode. Extremely hardcore.'],
    reroute: ['Actually, change of plans. Take me to {dest}.', 'New idea. {dest}. Now.'],
    dropoff: ['Massive tip incoming. Next year.', 'Tip is coming. Two weeks, max.'],
    walkout: ["I'm going to buy this taxi company."],
    idle: ["I'm going to rename this street X.", 'The algorithm likes you.', 'I posted 400 times today. Light day.'],
  },
  safety: {
    pickup: ["Hello. Before we start, I'd like to go over the risks.", 'Hi. Could we keep it under the speed limit? For civilization?'],
    jump: ['That was not in the scaling policy.', 'I need a moment.', "Please don't do that again. For everyone."],
    nearMiss: ["I'm flagging that as a moderate-severity incident.", 'We should write that up.'],
    crash: ['This is exactly what I wrote about.', 'Okay. Incident report. Section four.'],
    drift: ["That's an uncontrolled capability gain."],
    slow: ['This is nice. Responsible.', 'Thank you. Truly.'],
    timeLow: ["It's fine. Being late is aligned."],
    dropoff: ["Thanks. I've written fourteen thousand words about this ride.", 'Thank you. That was largely safe.'],
    walkout: ["I understand. I'll walk. Carefully."],
    idle: ['Machines of loving grace. Not this one.', 'Have you considered a constitution? For driving?', "I'm optimistic, honestly. Cautiously."],
  },
};

const PRIORITY: Partial<Record<QuipEvent, number>> = {
  pickup: 3, dropoff: 3, walkout: 3, fired: 3, back: 3, reroute: 3, underwater: 3, jumpFirst: 2,
  crash: 2, safetyLow: 2, geyser: 2, bigAir: 2, jump: 1, nearMiss: 1, timeLow: 1, dash: 1,
};
const CHANCE: Partial<Record<QuipEvent, number>> = { jump: 0.8, nearMiss: 0.6, drift: 0.4, crash: 0.9, idle: 0.7, dash: 0.35, smash: 0.25 };

export type ShowQuip = (who: string, color: string, text: string, seconds: number, speaker: Speaker) => void;

export class QuipDirector {
  private bags = new Map<string, string[]>();
  private last = new Map<string, string>();
  private busyUntil = 0;
  private busyPriority = -1;
  private lastAt = -10;
  private queue: { at: number; speaker: Speaker; event: QuipEvent; vars?: Record<string, string> }[] = [];
  now = 0;

  constructor(private show: ShowQuip) {}

  say(speaker: Speaker, event: QuipEvent, opts: { delay?: number; vars?: Record<string, string>; force?: boolean } = {}) {
    if (!LINES[speaker][event]) return false;
    if (!opts.force && Math.random() > (CHANCE[event] ?? 1)) return false;
    if (opts.delay) {
      this.queue.push({ at: this.now + opts.delay, speaker, event, vars: opts.vars });
      return true;
    }
    const pri = PRIORITY[event] ?? 0;
    if (this.now < this.busyUntil && pri <= this.busyPriority && pri < 3) return false;
    if (pri < 2 && this.now - this.lastAt < 1.2) return false;
    let text = this.draw(speaker, event);
    for (const [k, v] of Object.entries(opts.vars ?? {})) text = text.replaceAll(`{${k}}`, v);
    const seconds = Math.min(5, Math.max(2.2, 1.4 + text.length * 0.05));
    const s = SPEAKERS[speaker];
    this.show(s.name, s.color, text, seconds, speaker);
    babble(text, s.pitch);
    this.busyUntil = this.now + seconds;
    this.busyPriority = pri;
    this.lastAt = this.now;
    return true;
  }

  update(now: number) {
    this.now = now;
    const due = this.queue.filter((q) => q.at <= now);
    this.queue = this.queue.filter((q) => q.at > now);
    for (const q of due) this.say(q.speaker, q.event, { vars: q.vars, force: true });
  }

  reset() {
    this.queue = [];
    this.busyUntil = 0;
  }

  private draw(speaker: Speaker, event: QuipEvent) {
    const key = `${speaker}.${event}`;
    let bag = this.bags.get(key);
    if (!bag || bag.length === 0) {
      bag = [...LINES[speaker][event]!].sort(() => Math.random() - 0.5);
      if (bag.length > 1 && bag[bag.length - 1] === this.last.get(key)) bag.unshift(bag.pop()!);
      this.bags.set(key, bag);
    }
    const line = bag.pop()!;
    this.last.set(key, line);
    return line;
  }
}
