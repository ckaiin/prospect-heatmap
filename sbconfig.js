// Supabase connection for cross-device sync.
//
// Both values are safe to commit and ship to the browser: the anon key is a
// PUBLISHABLE key, and row-level security in schema.sql is what actually keeps
// your notes private. The service-role key is the secret one — it never appears
// here, only in Edge Function secrets.
//
// Leave the placeholders in place to run fully offline (localStorage only).
// Fill them in from Supabase -> Project Settings -> API.
window.SB_CONFIG = {
  url:     "https://YOUR-PROJECT-REF.supabase.co",
  anonKey: "YOUR-ANON-KEY",
};
