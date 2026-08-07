# Backend setup (Supabase)

The map works with no backend at all — that's the default. Everything here is
opt-in, and each piece degrades to the current behaviour if you skip it or if it
breaks in the field.

| Piece | What it gets you | Works without it? |
|---|---|---|
| Schema + auth | Visit status & notes sync across phone/laptop | Yes — localStorage, one device |
| `refresh-openings` | SLA feed updates without a commit | Yes — weekly GitHub Action |
| `foot-traffic` | Real popular-times instead of modeled curves | Yes — modeled curves |

Total cost at your scale: **$0** on Supabase's free tier, plus whatever you
choose to spend on BestTime (it has a free tier to evaluate).

---

## 1. Create the project

1. <https://supabase.com> → New project. Pick the region closest to NY
   (`us-east-1`). Save the database password somewhere.
2. **Project Settings → API**, copy the **Project URL** and the **anon public**
   key into `sbconfig.js` at the repo root:

   ```js
   window.SB_CONFIG = {
     url:     "https://abcdefgh.supabase.co",
     anonKey: "eyJhbGciOi...",
   };
   ```

   Both are safe to commit — the anon key is publishable, and row-level security
   is what actually protects your notes. The **service role** key is the secret
   one; it never goes in this file.

3. Commit and push. Sync appears in the panel as a status dot + email box.

## 2. Apply the schema

**SQL Editor → New query →** paste all of `schema.sql` → **Run**. Safe to re-run.

That creates `venue_notes` (private, RLS-guarded), `openings` and `foot_traffic`
(public read, service-role write).

## 3. Turn on sign-in

**Authentication → Providers → Email**: enable it, and turn ON *Confirm email*.
Magic links need no password.

**Authentication → URL Configuration → Redirect URLs**, add both:

```
https://ckaiin.github.io/prospect-heatmap/
http://localhost:8899/index.html
```

Sign-in flow: type your email in the panel → click the emailed link → the tab
comes back signed in, and stays that way. Do it once per device.

> Supabase's built-in email sender is rate-limited to a few messages an hour.
> That's fine for signing in twice, but if you start hitting it, add any SMTP
> provider under **Project Settings → Auth → SMTP**.

## 4. Deploy the Edge Functions

```bash
brew install supabase/tap/supabase     # once
supabase login
supabase link --project-ref <your-project-ref>

supabase functions deploy refresh-openings
supabase functions deploy foot-traffic
```

`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are injected automatically.

### Schedule the openings refresh

**Database → Extensions**: enable `pg_cron` and `pg_net`. Then uncomment the
final block in `schema.sql`, substitute your project ref and service-role key,
and run it. Verify with:

```sql
select * from cron.job_run_details order by start_time desc limit 5;
```

Once you've confirmed a successful run, retire the GitHub Action:

```bash
git rm .github/workflows/refresh-openings.yml
```

**Keep `openings_feed.py`.** It's the reference implementation, it still works
for local runs, and the Edge Function is a port of it — if the two ever
disagree, the Python is right.

### Real foot traffic (optional)

```bash
supabase secrets set BESTTIME_KEY=pri_your_private_key
```

Get the key at <https://besttime.app>. Without it the function returns
`unavailable` and the charts keep their modeled curves — no errors, no empty
charts. Forecasts are cached 30 days in `foot_traffic` because each live fetch
costs a credit.

Not every venue is covered. Coverage is best for established places with real
Google presence, worst for pre-opening venues — which is exactly where the
modeled curve stays useful.

---

## Checking it works

- **Sync**: sign in on two devices, change a status on one, reload the other.
  The dot goes green and reads "Synced across devices".
- **Offline**: turn off wifi, log a visit — it still saves, the row shows
  "N queued", and it flushes when you reconnect.
- **Openings**: `select count(*) from openings;` should be ~130–150.
- **Foot traffic**: open a popup for an established restaurant; the footnote
  changes to "Real foot-traffic forecast (BestTime)".

## When something looks wrong

The map is built to fail quietly toward "still usable", which means problems
show up as *missing* features rather than errors. Check the browser console
first — the sync layer logs `[sync]` warnings for every failure path, and a
missing `opening_hours` parser logs `[heatmap]`.

| Symptom | Likely cause |
|---|---|
| Dot stays grey after clicking the emailed link | Redirect URL not in the allow-list (step 3) |
| "Sync problem" in red | Schema not applied, or RLS policy missing |
| Notes not appearing on the other device | Not signed in as the same email |
| Openings count is 0 | Function not deployed, or cron not scheduled |
| Footnote never says "Real foot-traffic" | `BESTTIME_KEY` unset, or venue not covered |
