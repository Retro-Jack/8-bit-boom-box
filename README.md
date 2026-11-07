# 8-Bit Boom Box

> **Beta — v0.1.0-beta.** It works, and it is driving a real emulator, but it
> has only ever been fitted to one machine. The `machine` adapter is the part
> most likely to want changing once a second one is wired up, so treat its
> shape as provisional and pin a commit if you depend on it.

A cassette deck for an emulated 8-bit machine. It is a photographic boombox
that sits beside your emulator, takes tape files, drives the transport, and
tells the person at the keyboard what is going on while a program loads.

It exists because loading from tape is mostly **dead time**. The machine's
screen shows a filename and then nothing for a minute or more, and a visitor
who has never waited for a tape cannot tell *loading* from *finished* from
*crashed*. The deck answers that: the reels turn while the tape runs, a bar
fills, and the readout says in words what the transport is doing.

```
    ┌─────────────────────────┐
    │       Playing.          │
    │ ----------------------- │
    │     MasterMind.bas      │
    │ [##########=========]   │
    │ ----------------------- │
    │  20 files on the tape,  │
    │      in that order.     │
    └─────────────────────────┘
```

Open `index.html` over HTTP and you get a working demo driven by a stand-in
machine — no emulator needed.

```sh
python3 -m http.server 8001      # then visit http://127.0.0.1:8001/
```

It must be served over HTTP. It is an ES module and it fetches `regions.json`,
and browsers block both for `file://` pages.

## Using it

```html
<link rel="stylesheet" href="boombox.css">
<div id="deck"></div>
```

```js
import { createBoomBox } from './boombox.js';

const regions = await fetch('art/regions.json').then(r => r.json());
const deck = createBoomBox({ mount: document.getElementById('deck'), machine, regions });

function frame() {
  emulator.runFrame();
  deck.frame();            // once per emulated frame
  requestAnimationFrame(frame);
}
```

The deck builds its own markup inside `mount`, including a hidden file input,
and places the reels, the readout and the six keys from `regions.json`. You
decide where the deck goes and how wide it is; its height comes from the
artwork, so set a width and leave the rest alone.

### Options

| | |
| --- | --- |
| `mount` | the element the deck is built into. Required. |
| `machine` | the adapter below. Required. |
| `regions` | `art/regions.json`. Without it nothing is positioned inside the deck. |
| `art` | where the images live, default `art/`. |
| `accept` | the file input's `accept`, e.g. `.bas,.bin`. Default: anything. |
| `saveName` | fallback name for a saved recording, default `tape`. |
| `saveExt` | extension for a saved recording, default `.bin`. |
| `text` | any of the messages below, to override. |

### What it returns

`frame()` — call once per emulated frame.
`insert(name, bytes)` — put a file on the tape without the picker.
`eject()`, `play()`, `hint(line)`, `refresh()`.
`parts`, `engaged`, `element`.

## The machine adapter

This is the whole interface between the deck and your emulator. The deck
reads it; it never reaches past it.

| | |
| --- | --- |
| `motor` | **required.** Truthy while the tape should be moving. |
| `tape` | **required.** `null`, or `{ progress: 0..1, played: boolean }`. |
| `loadTape(bytes)` | **required.** Start playing this tape into the machine. |
| `ejectTape()` | **required.** Take it out. |
| `hasRecording` | truthy when there is something to save. Enables the record key. |
| `recordedTape()` | the recorded bytes, as a `Uint8Array`. |
| `tapeName(bytes)` | a name for the saved file, without extension. |
| `isTape(bytes)` | false if a picked file is not a tape recording. |
| `atPrompt()` | true when the machine is sitting at its prompt. |

Three of these deserve a word, because they are the ones that make the deck
worth having.

**`motor`, not a progress callback.** The deck watches the transport rather
than being told about it, because the states worth showing are ones a machine
passes through without announcing. A load is not one continuous run of tape:
the ROM stops the motor between blocks while it stows one away, and on a long
program that pause is easily long enough to look like a fault. The deck
notices and says **Please wait.**

**`played`, not `finished`.** A machine typically stops the motor on the last
block and never runs out the gap tone behind it, so the signal never ends on
its own. `played` means the data has gone past, which is when there is
nothing left to say.

**`atPrompt()` is worth implementing properly.** On a tape with more than one
file, the machine reads the first and returns to its prompt, where it will sit
until told what to do — forever, as far as a visitor can tell. The deck says
so, but only if it can tell *at the prompt* from *between blocks*, and the
transport alone cannot: measured on a real three-file load, the gaps between
blocks ran 0.18s, 2.70s and 3.72s, while the stop at the prompt ran 69s. A
threshold of 3s fired inside the 3.72s gap and told the user to type something
while the tape was still running. If your machine can be asked directly —
ours finds its cursor character in video RAM — ask it. Omit `atPrompt` and the
deck simply never offers that line, which is better than offering it wrongly.

## The messages

Every line is replaceable through `text`, because the deck does not know what
your machine's load command is called.

| key | default |
| --- | --- |
| `noTape` | `No tape` |
| `insert` | `Press eject to insert` |
| `load` | `Type  LOAD ""  then press play.` |
| `parts(n)` | `N programs on the tape, in that order.` |
| `notTape(name)` | `NAME is not a tape file.` |
| `playing` | `Playing.` |
| `rewound` | `Rewound; playing from the start.` |
| `wait` | `Please wait.` |
| `between` | `Waiting. Type  RUN  or  LOAD ""  for the next part.` |
| `nothing` | `Nothing recorded.` |
| `saved(name, n)` | `Saved NAME, N bytes.` |
| `count(n)` | `N files on the tape,` |
| `order` | `in that order.` |

`between` deliberately names two commands. A plain multi-file tape wants the
load command again; a tape fronted by a loader, which is most of them, wants
RUN and then fetches the rest itself. The deck cannot know which, so it does
not pretend to.

## The readout

It is a real character grid: **seven rows of twenty-one columns**, built as
CSS grid tracks so the rows are equal because the grid makes them so, rather
than because a line-height was tuned until they looked it. Each line is pinned
to its own row, so a line that is hidden leaves its row empty instead of
pulling the others up.

Type is one row high. The face's ascent and descent come to exactly 1em, so
the character grid and the glyph grid are the same grid, and columns come from
`ch` so they track the advance the rasteriser actually uses.

Lines longer than twenty-one characters scroll, **a character at a time** — a
real readout shifts its buffer by a cell and has no way to move half of one.
The travel is exactly one period, so a `steps()` of the period's character
count lands on whole cells at any text length or window size.

## The keys

Six, placed from `regions.json`, each lighting up when pressed.

**Eject** does double duty, which is what the two symbols moulded on it say:
with nothing in the deck it opens the file picker, with a tape in it ejects
the tape and every part of it. **Next** adds another file to the same tape —
a multi-part title is just files one after another, so the tape is a list and
they are concatenated. **Rew** restarts from the beginning, **play** starts
it, and **rec** downloads whatever the machine has recorded. **FF** is not
wired to anything; there is nothing sensible for it to do to a tape that is
already a byte array.

## The artwork

`art/deck.webp` is the deck with a cassette in it; `art/deck-empty.webp` is
the same deck with the bay empty, showing spindles, heads, capstan and pinch
roller. They are two photographs of the same machine, both in the document
from the start and swapped by a class, so the bay does not arrive a frame late
the first time a tape is ejected.

`tools/make-deck-empty.py` rebuilds the empty one from
`art/src/QFX-boombox-empty-bay.png` and `art/deck.webp`. Both are committed,
so it runs from a fresh clone with nothing fetched. It is doing more than a
collage — the source render is a different colour grade, its spindles sit in
the wrong place, and the wells they leave behind have to be painted out. The
script's own header explains each; the short version is that every number in
it was measured rather than chosen, and it prints a residual so drift shows up
as a number rather than as a surprise.

`tools/debrand.py` is the record of taking another project's markings off the
deck. It has already been applied to the committed artwork.

## Licence

GPL-3.0-or-later; see `COPYING`.
