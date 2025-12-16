
====================================================================
1) User
**A person with an account in Deepwork.**
**Fields:**

id – unique identifier (UUID or int).
email – login + contact.
created_at
plan – "free" or "paid" (from Gumroad key). 
license_key_id – link to license if they paid.

Free: Up to 100 minutes/day (4 × 25 min sessions), no AI, no analytics.
Paid: unlimited sessions, AI debrief, analytics.
====================================================================
**2) Session**
“One Deepwork block the user starts and finishes.”
Fields:

id
user_id
task – what they typed: “Implement SKAO parser v2”.
category – "coding" | "writing" | "study" | "other" (string for now).
start_time
end_time (nullable until finished).
planned_duration_minutes – 25/50/90 etc.
actual_duration_minutes – computed at end.
discipline_score – simple numeric score (we’ll compute later).
====================================================================
**3) DistractionEvent
“Each time the user tried to open a blocked site during a session.”
Fields:**

id
session_id
user_id
url – domain or full URL.
created_at

This is your gold – tells you how often they try to escape.
====================================================================
**4) LicenseKey
“Represents a paid purchase (e.g. from Gumroad) used to unlock full access.”
Fields:**

id
key – the string they paste in.
is_used – bool (if you want one-time use).
user_id – who claimed it (nullable if unused).
created_at

====================================================================
====================================================================