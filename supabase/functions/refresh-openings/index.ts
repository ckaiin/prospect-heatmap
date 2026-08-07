// Weekly refresh of the NY SLA new-openings feed, server-side.
//
// This is a port of openings_feed.py + fit.py. The Python remains the reference
// implementation and still works for local runs; keep the two in step if you
// change the fit heuristic.
//
// Invoked by pg_cron (see schema.sql). Requires the service-role key, because
// public.openings has no write policy — only service role bypasses RLS.
//
// Deploy: supabase functions deploy refresh-openings
// Test:   curl -X POST -H "Authorization: Bearer $SERVICE_ROLE_KEY" \
//              https://<ref>.supabase.co/functions/v1/refresh-openings

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";

const COUNTY = "Westchester";
const SLA_PENDING =
  `https://data.ny.gov/resource/f8i8-k2gm.json?premises_county=${COUNTY}&$limit=2000`;
const SLA_ACTIVE = "https://data.ny.gov/resource/9s3h-dpkz.json";
const CENSUS_ONELINE =
  "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress";

const RECENT_DAYS = 60;
const KEEP = new Set(["Restaurant", "Tavern", "Catering Establishment", "Summer Restaurant"]);

// ---- fit.py, ported ---------------------------------------------------------
const CHAINS = [
  "starbucks","dunkin","mcdonald","burger king","wendy","subway","chipotle","shake shack",
  "five guys","panera","chick-fil-a","kfc","popeyes","taco bell","domino","pizza hut",
  "papa john","little caesar","sbarro","wingstop","buffalo wild wings","ihop","applebee",
  "cheesecake factory","le pain quotidien","olive garden","red lobster","tgi friday",
  "chili's","denny","waffle house","dairy queen","sonic","arby","jersey mike","jimmy john",
  "firehouse subs","potbelly","qdoba","moe's southwest","sweetgreen","cava","blaze pizza",
  "& pizza","auntie anne","cinnabon","baskin","cold stone","crumbl","insomnia cookies",
  "cobs bread","pret a manger","tim horton","peet's","dutch bros","7-eleven","panda express",
  "checkers","white castle","boston market","smashburger","playa bowls","juice press",
  "european wax",
];
const NAME_UP = ["bistro","trattoria","osteria","brasserie","ristorante","tavern","chophouse",
  "steakhouse","steak house","oyster","wine bar","gastropub","kitchen","table","cellar",
  "brewpub","supper","patisserie","chocolat"];
const NAME_DOWN = ["bagel","donut","doughnut","juice bar","smoothie","creamery","ice cream",
  "frozen yogurt","coffee roast"];

// Openings carry no cuisine from SLA, so only the name signals apply here —
// same as the Python, which calls score_fit(name, "Restaurant", "").
function scoreFit(name: string): { fit: number; chain: boolean } {
  const n = (name || "").toLowerCase();
  if (CHAINS.some((c) => n.includes(c))) return { fit: 0, chain: true };
  let score = 60;                                   // BASE["Restaurant"]
  if (NAME_UP.some((w) => n.includes(w))) score += 10;
  if (NAME_DOWN.some((w) => n.includes(w))) score -= 10;
  return { fit: Math.max(30, Math.min(98, score)), chain: false };
}

const SUFFIXES = [" INC"," LLC"," CORP"," LTD"," CO"," LP"," INC."," CORP."," L L C"];
function niceName(raw: string): string {
  let n = (raw || "").trim();
  let up = n.toUpperCase();
  for (const s of SUFFIXES) {
    if (up.endsWith(s)) { n = n.slice(0, n.length - s.length); up = n.toUpperCase(); }
  }
  n = n.replace(/^[\s,]+|[\s,]+$/g, "");
  const isUniform = n === n.toUpperCase() || n === n.toLowerCase();
  return isUniform
    ? n.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())
    : n;
}

// Deterministic stand-in for the monthly-value estimate: same id always yields
// the same number, so values don't churn between refreshes.
//
// The Python uses md5, which WebCrypto doesn't offer, so this uses SHA-256 and
// therefore produces DIFFERENT numbers than openings_feed.py for the same venue.
// That's acceptable — monthlyValue is an unmodelled placeholder either way (see
// README) — but it does mean the "Pipeline $" totals shift once when you cut
// over to the backend feed. Don't chase the difference; replace the placeholder
// with a real estimate when there's something real to base it on.
async function det(seed: string): Promise<number> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode("val" + seed));
  const b = new Uint8Array(buf);
  return (((b[0] << 24) >>> 0) + (b[1] << 16) + (b[2] << 8) + b[3]) / 0xFFFFFFFF;
}

async function fetchJson(url: string) {
  const r = await fetch(url, {
    headers: { "User-Agent": "westchester-prospect-map/1.0 (personal prospecting tool)" },
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} for ${url}`);
  return await r.json();
}

// The Python uses the Census BATCH geocoder (multipart file upload). Deno's
// fetch can do that, but the batch endpoint is slow and flaky under a function
// timeout, so geocode one-by-one with bounded concurrency instead.
async function geocodeOne(addr: string, city: string, zip: string) {
  const q = encodeURIComponent(`${addr}, ${city}, NY ${zip}`.replace(/\s+/g, " ").trim());
  try {
    const j = await fetchJson(`${CENSUS_ONELINE}?address=${q}&benchmark=Public_AR_Current&format=json`);
    const m = j?.result?.addressMatches?.[0]?.coordinates;
    return m ? { lat: +(+m.y).toFixed(6), lng: +(+m.x).toFixed(6) } : null;
  } catch { return null; }
}

async function mapLimit<T, R>(items: T[], limit: number, fn: (t: T) => Promise<R>): Promise<R[]> {
  const out: R[] = new Array(items.length);
  let i = 0;
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (i < items.length) {
      const idx = i++;
      out[idx] = await fn(items[idx]);
    }
  }));
  return out;
}

Deno.serve(async (req) => {
  const started = Date.now();
  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    // ---- opening soon: pending licenses -----------------------------------
    const pending = (await fetchJson(SLA_PENDING))
      .filter((r: any) => KEEP.has(r.description));

    const geocoded = await mapLimit(pending, 6, async (r: any) => {
      const addr = (r.actual_address_of_premises || "").trim();
      const city = (r.city || "").trim();
      if (!addr || !city) return null;
      const c = await geocodeOne(addr, city, (r.zip_code || "").trim());
      return c ? { r, c, addr, city } : null;
    });

    const rows: any[] = [];
    const seen = new Set<string>();

    for (const g of geocoded) {
      if (!g) continue;
      const rawName = (g.r.dba || g.r.legalname || g.addr).trim();
      const name = g.r.dba ? rawName : niceName(rawName);
      const { fit, chain } = scoreFit(name);
      if (chain) continue;
      const appid = g.r.application_id || "";
      seen.add(`${g.c.lat.toFixed(4)},${g.c.lng.toFixed(4)}`);
      rows.push({
        id: "sla-" + appid,
        name,
        category: "Restaurant",
        cuisine: "",
        street: `${g.addr}, ${g.city}`,
        lat: g.c.lat,
        lng: g.c.lng,
        fit_score: fit,
        monthly_value: Math.floor((await det(appid)) * 2800),
        opening: {
          type: "soon",
          stage: g.r.status || "",
          received: (g.r.received_date || "").slice(0, 10),
          source: "NY SLA pending license",
        },
      });
    }

    // ---- just opened: recently issued active licenses ----------------------
    const cutoff = new Date(Date.now() - RECENT_DAYS * 864e5)
      .toISOString().slice(0, 10) + "T00:00:00";
    const descs = [...KEEP].sort().join("','");
    const where = `premisescounty='${COUNTY}' AND originalissuedate > '${cutoff}' ` +
                  `AND description in('${descs}')`;
    const active = await fetchJson(
      `${SLA_ACTIVE}?$limit=500&$where=${encodeURIComponent(where)}`);

    for (const r of active) {
      const geo = r.georeference?.coordinates;
      if (!geo) continue;
      const lng = +geo[0], lat = +geo[1];
      const key = `${lat.toFixed(4)},${lng.toFixed(4)}`;
      if (seen.has(key)) continue;                     // dedupe against pending
      seen.add(key);
      const name = niceName(r.legalname);
      const { fit, chain } = scoreFit(name);
      if (chain) continue;
      const lic = r.licensepermitid || "";
      rows.push({
        id: "sla-active-" + lic,
        name,
        category: "Restaurant",
        cuisine: "",
        street: `${(r.actualaddressofpremises || "").trim()}, ${(r.city || "").trim()}`
          .replace(/\b\w/g, (c: string) => c.toUpperCase()),
        lat: +lat.toFixed(6),
        lng: +lng.toFixed(6),
        fit_score: fit,
        monthly_value: Math.floor((await det(lic)) * 2800),
        opening: {
          type: "open",
          stage: "Recently opened",
          issued: (r.originalissuedate || "").slice(0, 10),
          source: "NY SLA new license",
        },
      });
    }

    if (!rows.length) throw new Error("feed returned 0 rows — refusing to wipe the table");

    // Upsert, stamping last_seen so aged-out openings are identifiable.
    const now = new Date().toISOString();
    const { error } = await supabase.from("openings")
      .upsert(rows.map((r) => ({ ...r, last_seen: now })), { onConflict: "id" });
    if (error) throw error;

    // Drop anything the feed hasn't mentioned in 90 days (SLA rolls records off).
    const stale = new Date(Date.now() - 90 * 864e5).toISOString();
    await supabase.from("openings").delete().lt("last_seen", stale);

    return Response.json({
      ok: true, upserted: rows.length,
      soon: rows.filter((r) => r.opening.type === "soon").length,
      open: rows.filter((r) => r.opening.type === "open").length,
      ms: Date.now() - started,
    });
  } catch (e) {
    console.error("[refresh-openings]", e);
    return Response.json({ ok: false, error: String(e) }, { status: 500 });
  }
});
