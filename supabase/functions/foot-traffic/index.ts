// Real foot-traffic forecasts, proxied so the API key never reaches the browser.
//
// Backed by BestTime.app, which licenses the underlying popular-times signal.
// (This is the reason not to scrape Google: same data, no ToS problem, no
// headless browser to babysit.)
//
// Forecasts cost credits, so every result is cached in public.foot_traffic and
// only refetched when older than TTL_DAYS. A venue's rhythm doesn't move much
// week to week; a month-old forecast is still a good forecast.
//
// Deploy:  supabase functions deploy foot-traffic
// Secret:  supabase secrets set BESTTIME_KEY=pri_xxxxxxxx
//
// Request:  POST { venue_id, name, address }
// Response: { source: "live"|"cache"|"unavailable", days: number[7][24] }  0..1
//           days[0] is Sunday, matching JS Date.getDay().

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";

const TTL_DAYS = 30;

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// BestTime returns Monday-first day_raw arrays of 24 ints (0-100); the map
// indexes by JS getDay() (Sunday-first), so rotate on the way through.
function toSundayFirst(mondayFirst: number[][]): number[][] {
  return [mondayFirst[6], ...mondayFirst.slice(0, 6)];
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

  try {
    const { venue_id, name, address } = await req.json();
    if (!venue_id || !name || !address) {
      return Response.json({ error: "venue_id, name and address are required" },
        { status: 400, headers: cors });
    }

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    // ---- cache ------------------------------------------------------------
    const { data: hit } = await supabase.from("foot_traffic")
      .select("days, fetched_at").eq("venue_id", venue_id).maybeSingle();

    if (hit?.days) {
      const ageDays = (Date.now() - new Date(hit.fetched_at).getTime()) / 864e5;
      if (ageDays < TTL_DAYS) {
        return Response.json({ source: "cache", days: hit.days }, { headers: cors });
      }
    }

    const key = Deno.env.get("BESTTIME_KEY");
    if (!key) {
      // No key configured: say so plainly so the client keeps its modeled curve
      // instead of rendering an empty chart.
      return Response.json({ source: "unavailable", reason: "BESTTIME_KEY not set" },
        { headers: cors });
    }

    // ---- live fetch -------------------------------------------------------
    const url = "https://besttime.app/api/v1/forecasts?" + new URLSearchParams({
      api_key_private: key, venue_name: name, venue_address: address,
    });
    const r = await fetch(url, { method: "POST" });
    const j = await r.json();

    if (!r.ok || j.status === "Error") {
      // Venue not covered is the common case, not a failure worth retrying hard.
      return Response.json({ source: "unavailable", reason: j.message || `HTTP ${r.status}` },
        { headers: cors });
    }

    const raw = (j.analysis || []).map((d: any) => d?.day_raw || []);
    if (raw.length !== 7 || raw.some((d: number[]) => d.length !== 24)) {
      return Response.json({ source: "unavailable", reason: "unexpected forecast shape" },
        { headers: cors });
    }

    const days = toSundayFirst(raw).map((d: number[]) => d.map((v) => +(v / 100).toFixed(3)));

    await supabase.from("foot_traffic").upsert({
      venue_id, name, address, days, fetched_at: new Date().toISOString(),
    }, { onConflict: "venue_id" });

    return Response.json({ source: "live", days }, { headers: cors });
  } catch (e) {
    console.error("[foot-traffic]", e);
    return Response.json({ source: "unavailable", reason: String(e) },
      { status: 500, headers: cors });
  }
});
