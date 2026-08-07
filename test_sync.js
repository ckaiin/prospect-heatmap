// Unit tests for the tracker merge. Run: node test_sync.js
// The merge is the only place a sync bug can silently eat a note, so it's the
// part that gets tested rather than the network plumbing around it.
const { mergeTracker } = require("./sync.js");

let pass = 0, fail = 0;
function eq(name, got, want) {
  const g = JSON.stringify(got), w = JSON.stringify(want);
  if (g === w) { pass++; console.log(`  ok  ${name}`); }
  else { fail++; console.log(`  FAIL ${name}\n       got  ${g}\n       want ${w}`); }
}

const L = (u, s, n) => ({ status: s, note: n, updated: u });

console.log("mergeTracker");

// Local-only entries must reach the server.
eq("local-only pushes up",
  mergeTracker({ a: L(100, "contacted") }, {}),
  { merged: { a: L(100, "contacted") }, toPush: { a: L(100, "contacted") } });

// Remote-only entries land locally and are not echoed back.
eq("remote-only pulls down",
  mergeTracker({}, { b: L(200, "customer") }),
  { merged: { b: L(200, "customer") }, toPush: {} });

// Newer local wins and is pushed.
eq("newer local wins",
  mergeTracker({ c: L(300, "customer") }, { c: L(200, "contacted") }),
  { merged: { c: L(300, "customer") }, toPush: { c: L(300, "customer") } });

// Newer remote wins and is NOT pushed back (that would ping-pong).
eq("newer remote wins, no echo",
  mergeTracker({ d: L(100, "new") }, { d: L(400, "customer") }),
  { merged: { d: L(400, "customer") }, toPush: {} });

// Equal timestamps: keep local, but don't generate write traffic.
eq("tie keeps local without pushing",
  mergeTracker({ e: L(500, "contacted") }, { e: L(500, "customer") }),
  { merged: { e: L(500, "contacted") }, toPush: {} });

// A note edited offline on one device must survive a pull from the other.
eq("offline note survives pull",
  mergeTracker({ f: L(900, "contacted", "owner is in Tues am") }, { f: L(800, "contacted", "") }),
  { merged: { f: L(900, "contacted", "owner is in Tues am") },
    toPush: { f: L(900, "contacted", "owner is in Tues am") } });

// Missing/զero timestamps must not throw or win over real ones.
eq("entry with no timestamp loses to a real one",
  mergeTracker({ g: { status: "new" } }, { g: L(50, "customer") }),
  { merged: { g: L(50, "customer") }, toPush: {} });

// Disjoint sets merge both directions in one pass.
eq("disjoint sets union correctly",
  mergeTracker({ h: L(10, "contacted") }, { i: L(20, "customer") }),
  { merged: { h: L(10, "contacted"), i: L(20, "customer") }, toPush: { h: L(10, "contacted") } });

// Empty on both sides is a no-op, not a crash.
eq("empty input", mergeTracker({}, {}), { merged: {}, toPush: {} });
eq("null input", mergeTracker(null, null), { merged: {}, toPush: {} });

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
