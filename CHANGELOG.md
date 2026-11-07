# Changelog

All notable changes to this project are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0-beta] - 07/11/2026

First public cut. Beta because it has only been fitted to one machine: the
`machine` adapter is the part most likely to change once a second one is
wired up.

### Added

- **First cut**, lifted out of the NewBrain emulator it was built in and made
  to stand on its own.

  The deck itself is unchanged in behaviour: the reels follow the motor, the
  readout is a seven-by-twenty-one character grid that scrolls a character at
  a time, the bay shows its own mechanism when there is no tape in it, and the
  three tape messages — **Please wait.** between blocks, the nudge when the
  machine has gone back to its prompt between files, and the line telling you
  how to get a tape in — all work as they did.

  What is new is the seam. In the emulator the deck reached into the machine
  in nine places: the motor line, the tape object, load and eject, the
  recording, the video RAM it scanned for a cursor, and the tape codec it
  asked whether a file was a recording at all. Those are now one documented
  `machine` adapter, and every word the deck says is replaceable, because the
  deck has no business knowing what your load command is called.

- **A demo that needs no emulator.** `index.html` drives the deck from a
  stand-in machine that reads at a steady rate, rests between blocks and
  returns to its prompt at the end of each file, with the timings measured off
  a real load. Every state the readout has is reachable from the three buttons
  under it.

- **The artwork, and the scripts that make it.** `tools/make-deck-empty.py`
  rebuilds the empty bay from the committed render and the committed deck, so
  it reproduces from a fresh clone — in the emulator it could not, because the
  source render was ignored by git. `tools/debrand.py` records what was taken
  off the deck to get it here.

### Changed

- **The readout names the file going past, not the whole tape.** Joining
  every part with " + " made the name long enough to scroll, and a name that
  is scrolling is a name you cannot read at a glance. Each part's offset in
  the concatenated tape is known, so the line names whichever file the tape
  is in, and changes as it crosses a boundary. A single filename too long for
  twenty-one columns still scrolls, which is the right fallback.

- **The deck carries no branding.** The logo on the left panel and the
  wordmark on the right belonged to the project it came from. Both are painted
  out, and the empty-bay image is rebuilt from the cleaned deck so the two
  agree.

### Notes

- The readout keeps its IDs (`#tapedeck`, `#tapewin`, `#twname` and the rest)
  rather than moving to classes, so one deck per page. That is all anyone has
  wanted so far and the geometry is carefully measured against those
  selectors; changing it is a job on its own, not a rename.
- **FF** is present on the panel and wired to nothing. There is no sensible
  thing for it to do to a tape that is already a byte array in memory.
