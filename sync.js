// Cross-device sync for the visit tracker (Supabase).
//
// Offline-first on purpose: you log visits in the field, where Westchester cell
// coverage is patchy. localStorage stays the source of truth for every write and
// the UI never waits on the network; the cloud is a replica that catches up.
//
// Merge is last-write-wins per venue on `updated`. Conflicts are rare in practice
// (one rep, a phone and a laptop) and a lost note is worse than a lost keystroke,
// so ties keep the local copy.
//
// Degrades to exactly the old behaviour when sbconfig.js has no credentials:
// the map works signed-out, storing to localStorage only.

(function () {
  "use strict";

  // `window` is absent under node, where test_sync.js loads this for the merge.
  const root = typeof window !== "undefined" ? window : {};
  const CFG = root.SB_CONFIG || {};
  const CONFIGURED = !!(CFG.url && CFG.anonKey && !/YOUR-/.test(CFG.url + CFG.anonKey));

  // ---- Pure merge (unit-tested in test_sync.js; no DOM, no network) ---------
  // local/remote: { venueId: {status, note, updated} }
  // Returns { merged, toPush } — toPush is the subset the server needs.
  function mergeTracker(local, remote) {
    const merged = {}, toPush = {};
    const ids = new Set([...Object.keys(local || {}), ...Object.keys(remote || {})]);
    ids.forEach(id => {
      const l = (local || {})[id], r = (remote || {})[id];
      if (l && !r) { merged[id] = l; toPush[id] = l; return; }
      if (r && !l) { merged[id] = r; return; }
      // Both sides have it: newer wins, local wins ties.
      if ((l.updated || 0) >= (r.updated || 0)) {
        merged[id] = l;
        // Only push if it's genuinely different, not just a tie.
        if ((l.updated || 0) > (r.updated || 0)) toPush[id] = l;
      } else {
        merged[id] = r;
      }
    });
    return { merged, toPush };
  }

  const rowToEntry = row => ({
    status: row.status || undefined,
    note: row.note || undefined,
    updated: row.updated_at ? new Date(row.updated_at).getTime() : 0,
  });
  const entryToRow = (userId, id, e) => ({
    user_id: userId,
    venue_id: id,
    status: e.status || null,
    note: e.note || null,
    updated_at: new Date(e.updated || Date.now()).toISOString(),
  });

  // ---- Client -------------------------------------------------------------
  const Sync = {
    configured: CONFIGURED,
    client: null,
    user: null,
    status: CONFIGURED ? "signed-out" : "off",   // off | signed-out | syncing | ok | error
    error: null,
    onChange: () => {},                          // set by index.html to re-render
    _queue: {},                                  // venueId -> entry, awaiting push
    _timer: null,

    async init() {
      if (!CONFIGURED) return;
      if (typeof supabase === "undefined") {
        this.status = "error";
        this.error = "supabase-js failed to load";
        console.error("[sync] supabase-js not loaded — sync disabled, local storage still works.");
        return this.onChange();
      }
      this.client = supabase.createClient(CFG.url, CFG.anonKey);
      const { data } = await this.client.auth.getSession();
      this.user = data.session ? data.session.user : null;
      this.status = this.user ? "syncing" : "signed-out";
      this.onChange();

      this.client.auth.onAuthStateChange((_e, session) => {
        this.user = session ? session.user : null;
        this.status = this.user ? "syncing" : "signed-out";
        this.onChange();
        if (this.user) this.pull();
      });

      if (this.user) await this.pull();
      // Catch up whatever queued while offline.
      root.addEventListener("online", () => this.flush());
      root.addEventListener("focus", () => { if (this.user) this.pull(); });
    },

    async signIn(email) {
      if (!this.client) return { error: "Sync isn't configured yet." };
      try {
        const { error } = await this.client.auth.signInWithOtp({
          email,
          options: { emailRedirectTo: root.location.href.split("#")[0] },
        });
        return { error: error ? error.message : null };
      } catch (e) {
        // A dead/misconfigured project surfaces as a bare "Failed to fetch",
        // which tells a rep in the field nothing useful.
        console.warn("[sync] sign-in failed", e);
        return { error: "Can't reach the server — check your connection (your notes are still saving on this device)." };
      }
    },

    async signOut() {
      if (this.client) await this.client.auth.signOut();
      this.user = null;
      this.status = "signed-out";
      this.onChange();
    },

    // Pull remote, merge into the live tracker, push anything local-newer.
    async pull() {
      if (!this.client || !this.user) return;
      this.status = "syncing"; this.onChange();
      try {
        const { data, error } = await this.client
          .from("venue_notes").select("venue_id,status,note,updated_at");
        if (error) throw error;

        const remote = {};
        (data || []).forEach(r => { remote[r.venue_id] = rowToEntry(r); });

        const local = root.TRACKER_SNAPSHOT ? root.TRACKER_SNAPSHOT() : {};
        const { merged, toPush } = mergeTracker(local, remote);

        if (root.TRACKER_APPLY) root.TRACKER_APPLY(merged);
        Object.assign(this._queue, toPush);
        await this.flush();

        this.status = "ok"; this.error = null;
      } catch (e) {
        this.status = "error"; this.error = String(e.message || e);
        console.warn("[sync] pull failed — working locally.", e);
      }
      this.onChange();
    },

    // Queue a single venue's change; pushes are debounced and survive offline.
    push(venueId, entry) {
      if (!this.client || !this.user) return;
      this._queue[venueId] = entry;
      clearTimeout(this._timer);
      this._timer = setTimeout(() => this.flush(), 800);
    },

    async flush() {
      if (!this.client || !this.user) return;
      const ids = Object.keys(this._queue);
      if (!ids.length) return;
      const rows = ids.map(id => entryToRow(this.user.id, id, this._queue[id]));
      try {
        const { error } = await this.client
          .from("venue_notes").upsert(rows, { onConflict: "user_id,venue_id" });
        if (error) throw error;
        ids.forEach(id => delete this._queue[id]);   // only clear on success
        this.status = "ok"; this.error = null;
      } catch (e) {
        this.status = "error"; this.error = String(e.message || e);
        console.warn("[sync] push failed — queued, will retry.", e);
      }
      this.onChange();
    },

    pending() { return Object.keys(this._queue).length; },

    // ---- Backend openings feed --------------------------------------------
    // openings.js stays the baseline so the map renders instantly and works
    // offline; this refreshes on top of it when the backend has newer data.
    // Returns rows in the same shape as window.REAL_OPENINGS, or null.
    async fetchOpenings() {
      if (!this.client) return null;
      try {
        const { data, error } = await this.client.from("openings")
          .select("id,name,category,cuisine,street,lat,lng,fit_score,monthly_value,opening");
        if (error) throw error;
        if (!data || !data.length) return null;
        return data.map(r => ({
          id: r.id, name: r.name, category: r.category, cuisine: r.cuisine || "",
          street: r.street, lat: r.lat, lng: r.lng,
          fitScore: r.fit_score, monthlyValue: r.monthly_value,
          status: "new", opening: r.opening,
        }));
      } catch (e) {
        console.warn("[sync] openings fetch failed — using bundled openings.js.", e);
        return null;
      }
    },

    // ---- Real foot traffic (BestTime via Edge Function) --------------------
    // Resolves to {days:[7][24]} or null. Null means "keep the modeled curve".
    async footTraffic(venue) {
      if (!this.client) return null;
      const key = String(venue.id);
      if (this._ft && key in this._ft) return this._ft[key];
      this._ft = this._ft || {};
      try {
        const { data, error } = await this.client.functions.invoke("foot-traffic", {
          body: { venue_id: key, name: venue.name, address: venue.street },
        });
        if (error) throw error;
        this._ft[key] = data && data.days ? data.days : null;
      } catch (e) {
        console.warn("[sync] foot-traffic lookup failed — using modeled curve.", e);
        this._ft[key] = null;
      }
      return this._ft[key];
    },
  };

  Sync.mergeTracker = mergeTracker;               // exposed for tests
  root.Sync = Sync;
  if (typeof module !== "undefined" && module.exports) module.exports = { mergeTracker };
})();
