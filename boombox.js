// SPDX-License-Identifier: GPL-3.0-or-later
//
// 8-Bit Boom Box — a cassette deck for an emulated 8-bit machine.
//
// The deck knows about tapes and transports. It knows nothing about any
// particular machine: everything it needs from one arrives through the
// `machine` adapter described in the README, and every word it says can be
// replaced through `text`. That boundary is the whole point of the library,
// so resist reaching through it.
//
// Call `frame()` once per emulated frame. The deck reads the transport then
// rather than being told, because the things worth showing -- the motor
// stopping between blocks, the tape reaching its end -- are states the
// machine passes through without announcing.

const GAP = '   ·   ';
const CELLS = 19;          // plus two brackets is 21, the full grid width
const BLINK = 800;         // how long a prompt sighting counts for
const KEY_NAMES = ['eject', 'next', 'rew', 'play', 'ff', 'rec'];

const DEFAULT_TEXT = {
  noTape: 'No tape',
  insert: 'Press eject to insert',
  load: 'Type  LOAD ""  then press play.',
  parts: (n) => `${n} programs on the tape, in that order.`,
  notTape: (name) => `${name} is not a tape file.`,
  playing: 'Playing.',
  rewound: 'Rewound; playing from the start.',
  wait: 'Please wait.',
  between: 'Waiting. Type  RUN  or  LOAD ""  for the next part.',
  nothing: 'Nothing recorded.',
  saved: (name, n) => `Saved ${name}, ${n} bytes.`,
  count: (n) => `${n} file${n === 1 ? '' : 's'} on the tape${n > 1 ? ',' : '.'}`,
  order: 'in that order.',
};

const MARKUP = `
  <img class="loaded" alt="">
  <img class="bare" alt="">
  <i></i>
  ${KEY_NAMES.map((k) => `<span class="key" data-key="${k}"></span>`).join('\n  ')}
  <div id="tapewin" class="nohint notape" aria-hidden="true">
    <div id="twhint"><span></span></div>
    <div id="twsep"></div>
    <div id="twname"><span></span></div>
    <div id="twbar"></div>
    <div id="twrule"></div>
    <div id="twcount"></div>
    <div id="twnote"></div>
  </div>`;

export function createBoomBox(options) {
  const {
    mount,
    machine,
    regions,
    text: textIn = {},
    art = 'art/',
    accept = '',
    saveName = 'tape',
    saveExt = '.bin',
  } = options;

  const text = { ...DEFAULT_TEXT, ...textIn };
  const want = (fn, name) => {
    if (typeof machine?.[fn] !== 'function') {
      throw new Error(`8-bit-boom-box: machine.${name || fn}() is required`);
    }
  };
  want('loadTape');
  want('ejectTape');

  // ---- markup ------------------------------------------------------------
  const el = mount;
  el.id = 'tapedeck';
  el.classList.add('empty');
  el.innerHTML = MARKUP;
  el.querySelector('img.loaded').src = art + 'deck.webp';
  el.querySelector('img.bare').src = art + 'deck-empty.webp';

  const file = document.createElement('input');
  file.type = 'file';
  file.multiple = true;
  file.hidden = true;
  if (accept) file.accept = accept;
  el.appendChild(file);

  const win = el.querySelector('#tapewin');
  const twHint = el.querySelector('#twhint');
  const twName = el.querySelector('#twname');
  const twBar = el.querySelector('#twbar');
  const twCount = el.querySelector('#twcount');
  const twNote = el.querySelector('#twnote');
  const keys = {};
  for (const k of KEY_NAMES) keys[k] = el.querySelector(`.key[data-key="${k}"]`);

  // ---- placement ---------------------------------------------------------
  // A region inside the deck is a percentage of the deck, so it needs nothing
  // from the page and survives the deck being moved or resized.
  const within = (node, r) => {
    node.style.left = r.left + '%';
    node.style.top = r.top + '%';
    node.style.width = r.width + '%';
    node.style.height = r.height + '%';
  };
  if (regions) {
    within(el.querySelector('i'), regions.reels);
    within(win, regions.window);
    for (const [k, r] of Object.entries(regions.buttons)) within(keys[k], r);
  }

  // ---- state -------------------------------------------------------------
  const deck = {
    // A cassette holds programs one after another, and a multi-part title is
    // exactly that: a loader followed by the binary it asks for. So the tape
    // is a LIST of files, concatenated, and the machine reads them in turn.
    parts: [],
    bytes: null,
    // Where each part starts in the concatenated tape, so the readout can
    // say which file is going past rather than listing them all.
    offsets: [],
    total: 0,
    showing: -1,
    // The reels turn only once the transport has been engaged from the
    // panel. The motor line alone will not do: on a real machine, asking it
    // to load raises the motor and holds it high while it waits for a
    // signal, with nothing in the deck and nothing moving -- so the reels
    // would spin at a stopped tape.
    engaged: false,
    waiting: undefined,
    cursorAt: undefined,
    promptShown: false,
  };
  const can = { eject: true, next: false, rew: false, play: false, rec: false };

  // ---- the readout -------------------------------------------------------
  // A line, scrolled only when it will not fit.
  //
  // The separator goes on the end of BOTH copies, not between them. Written
  // as text+gap+text the span is 2*text+gap wide, so translating -50% moves
  // text+gap/2 -- half a separator short of one period, and it jumps by that
  // much every time round. Written as (text+gap)+(text+gap) the halves are
  // identical, -50% is exactly one period, and the loop closes.
  function fit(box, line) {
    const span = box.firstElementChild;
    span.textContent = line;
    box.classList.remove('scroll');
    span.style.animationDuration = '';
    span.style.animationTimingFunction = '';
    if (!line) return;
    requestAnimationFrame(() => {
      if (span.scrollWidth - box.clientWidth <= 1) return;
      const period = line + GAP;
      span.textContent = period.repeat(2);
      box.classList.add('scroll');
      // A steady reading pace whatever the length: one pass takes as long as
      // the text is wide.
      span.style.animationDuration = (span.scrollWidth / 2 / 26).toFixed(1) + 's';
      // Stepped, not smooth: one step per character in the period moves the
      // line a whole cell at a time, which is the only way a character
      // display can move anything.
      span.style.animationTimingFunction = `steps(${period.length})`;
    });
  }

  function hint(line) {
    fit(twHint, line || '');
    win.classList.toggle('nohint', !line);
  }

  function progress(frac) {
    if (frac === null) {
      twBar.textContent = '';
      return;
    }
    const lit = Math.max(0, Math.min(CELLS, Math.round(frac * CELLS)));
    twBar.textContent = '[' + '#'.repeat(lit) + '='.repeat(CELLS - lit) + ']';
  }

  function paint() {
    const n = deck.parts.length;
    win.classList.toggle('notape', !n);
    el.classList.toggle('empty', !n);
    // Not just the state but the remedy: the eject key is how a tape gets
    // in, and that is only discoverable from a tooltip, which is a hover
    // away and no use at all on a phone. It is said across two lines, the
    // second borrowing the count's row.
    progress(n ? (machine.tape ? machine.tape.progress : 0) : null);
    // One sentence across two rows, so the count takes the comma and the
    // note finishes it. With a single file there is no note to finish it,
    // so that line ends in a stop instead of a dangling comma.
    twCount.textContent = n ? text.count(n) : text.insert;
    twNote.textContent = n > 1 ? text.order : '';
    deck.showing = currentPart();
    fit(twName, n ? deck.parts[deck.showing].name : text.noTape);
  }

  function refresh() {
    const loaded = !!deck.bytes;
    const playing = !!machine.tape;
    can.eject = true; // insert when empty, eject when not
    can.next = loaded;
    can.play = loaded && !playing;
    can.rew = playing;
    can.rec = !!machine.hasRecording;
    for (const [name, node] of Object.entries(keys)) node.classList.toggle('off', !can[name]);
    paint();
  }

  // ---- the transport -----------------------------------------------------
  function rebuild() {
    const total = deck.parts.reduce((n, p) => n + p.bytes.length, 0);
    deck.offsets = [];
    deck.total = total;
    deck.showing = -1;
    if (!total) {
      deck.bytes = null;
      return;
    }
    const tape = new Uint8Array(total);
    let at = 0;
    for (const p of deck.parts) {
      deck.offsets.push(at);
      tape.set(p.bytes, at);
      at += p.bytes.length;
    }
    deck.bytes = tape;
  }

  // Which file is going past. The readout names that one rather than the
  // whole tape: a three-part title joined with " + " is far too long for
  // twenty-one columns, so it scrolled, and a name that is scrolling is a
  // name you cannot read at a glance. One file at a time fits.
  //
  // At a boundary the offset lands on the next part's first byte, which is
  // the right answer: the file just read is finished with, and the one the
  // machine is about to be asked for is the one worth naming.
  function currentPart() {
    const n = deck.parts.length;
    if (!n) return -1;
    const at = machine.tape ? machine.tape.progress * deck.total : 0;
    let i = 0;
    while (i < n - 1 && at >= deck.offsets[i + 1]) i++;
    return i;
  }

  function arm() {
    deck.engaged = true;
    deck.waiting = undefined;
    deck.cursorAt = undefined;
    deck.promptShown = false;
  }

  function play() {
    arm();
    machine.loadTape(deck.bytes);
    hint(text.playing);
  }

  function rewind() {
    arm();
    machine.loadTape(deck.bytes);
    hint(text.rewound);
  }

  function eject() {
    deck.engaged = false;
    machine.ejectTape();
    deck.parts = [];
    deck.bytes = null;
    deck.offsets = [];
    deck.total = 0;
    deck.showing = -1;
    file.value = '';
    progress(null);
    hint('');
  }

  // Hands back whatever the machine has written to tape, as a download.
  function save() {
    if (typeof machine.recordedTape !== 'function') return;
    const bytes = machine.recordedTape();
    if (!bytes || !bytes.length) {
      hint(text.nothing);
      return;
    }
    deck.engaged = true;
    const name =
      (typeof machine.tapeName === 'function' && machine.tapeName(bytes)) || saveName;
    const url = URL.createObjectURL(new Blob([bytes], { type: 'application/octet-stream' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = name + saveExt;
    a.click();
    URL.revokeObjectURL(url);
    hint(text.saved(name + saveExt, bytes.length));
  }

  // ---- keys --------------------------------------------------------------
  // Eject does double duty, which is what the two symbols moulded on it say:
  // with nothing in the deck it opens the file picker, and with a tape in it
  // ejects that tape and every part of it.
  const action = {
    eject: () => (deck.parts.length ? eject() : file.click()),
    next: () => file.click(),
    rew: rewind,
    play,
    ff: null,
    rec: save,
  };

  for (const [name, node] of Object.entries(keys)) {
    node.addEventListener('click', () => {
      if (!can[name] || !action[name]) return;
      // Play stays down for as long as the tape runs, so it is left to
      // frame(); the rest are momentary and flash.
      if (name !== 'play') {
        node.classList.add('down');
        setTimeout(() => node.classList.remove('down'), 170);
      }
      action[name]();
      refresh();
    });
  }

  file.addEventListener('change', async () => {
    const picked = [...file.files];
    if (!picked.length) return;
    const first = !deck.parts.length;
    for (const f of picked) {
      deck.parts.push({ name: f.name, bytes: new Uint8Array(await f.arrayBuffer()) });
    }
    rebuild();
    machine.ejectTape();
    progress(0);
    refresh();
    // A file that is not a tape recording contributes nothing, and would go
    // on silently and not be there. Say so rather than let it look loaded.
    const bad =
      typeof machine.isTape === 'function'
        ? deck.parts.filter((p) => !machine.isTape(p.bytes))
        : [];
    if (bad.length) hint(text.notTape(bad[0].name));
    else hint(first ? text.load : text.parts(deck.parts.length));
    file.value = '';
    file.blur();
  });

  // ---- per-frame ---------------------------------------------------------
  function frame() {
    const tape = machine.tape;
    // The reels follow the motor, but only once play or save has been
    // pressed -- before that the deck is stopped however the motor reads.
    el.classList.toggle('on', deck.engaged && !!machine.motor);
    keys.play.classList.toggle('down', deck.engaged && !!tape && !tape.played);
    if (can.rec !== !!machine.hasRecording) refresh();
    if (!tape) return;
    progress(tape.progress);

    // Name the file the tape is in now, and only re-set it when it changes --
    // fit() restarts the scroll, so calling it every frame would peg a long
    // name to its first character for ever.
    const part = currentPart();
    if (part !== deck.showing && part >= 0) {
      deck.showing = part;
      fit(twName, deck.parts[part].name);
    }

    if (deck.engaged && !tape.played) {
      // A load is not one continuous run of tape: the machine stops the
      // motor between blocks while it digests what it has just read, and on
      // a long program that pause is easily long enough to look like a
      // fault. Only transitions are announced, and the first reading is
      // adopted in silence, so this cannot talk over the hint the button
      // press just set.
      const waiting = !machine.motor;
      if (deck.waiting === undefined) deck.waiting = waiting;
      else if (waiting !== deck.waiting) {
        deck.waiting = waiting;
        hint(waiting ? text.wait : text.playing);
      }

      // Stopped with tape still to come, on a tape with more than one file,
      // and the machine back at its prompt: it has finished a file and will
      // sit there until told what to do next. Nobody is coming to tell them.
      //
      // It does not say which command, because the deck cannot know. A plain
      // multi-file tape wants its load command again; a tape fronted by a
      // loader, which is most of them, wants RUN and fetches the rest
      // itself.
      if (waiting && deck.parts.length > 1 && typeof machine.atPrompt === 'function') {
        if (machine.atPrompt()) deck.cursorAt = performance.now();
        const atPrompt =
          deck.cursorAt !== undefined && performance.now() - deck.cursorAt < BLINK;
        if (atPrompt && !deck.promptShown) {
          deck.promptShown = true;
          hint(text.between);
        }
      } else {
        deck.cursorAt = undefined;
        deck.promptShown = false;
      }
    }

    // `played`, not `finished`: a machine typically stops the motor on the
    // last block and never runs out the gap tone behind it, so the signal
    // never ends on its own. Once the data has gone past there is nothing
    // left to say, so the status clears rather than sitting on "playing".
    if (tape.played && !deck.doneShown) {
      deck.doneShown = true;
      hint('');
      refresh();
    } else if (!tape.played) {
      deck.doneShown = false;
    }
  }

  refresh();

  return {
    frame,
    hint,
    refresh,
    insert(name, bytes) {
      deck.parts.push({ name, bytes: new Uint8Array(bytes) });
      rebuild();
      machine.ejectTape();
      progress(0);
      refresh();
    },
    eject,
    play,
    get parts() {
      return deck.parts.slice();
    },
    get engaged() {
      return deck.engaged;
    },
    element: el,
  };
}
