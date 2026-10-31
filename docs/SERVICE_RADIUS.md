# Reviewer service radius

New reviewer assignments use a maximum straight-line distance of 50 km from
the reviewer's saved home coordinates to the property's coordinates.
Exactly 50 km is allowed; greater distances are excluded before rounding.

GET /jobs/open hides jobs beyond the service radius. Its max_distance_km query
parameter can narrow the results but cannot expand the configured service area.
POST /jobs/{id}/accept independently enforces the same rule, returning 400
before assigning a reviewer or creating payment, ledger or notification records.

Set MAX_SERVICE_DISTANCE_KM to a positive finite number in .env to change the
radius, then restart the server. The default is 50. Invalid values fail startup.
Pricing remains INR 100 plus INR 10 per km, calculated at acceptance.
There is no database migration, repricing or modification of historical jobs.
Existing job detail visibility, accepted jobs and completed payments are retained.

This uses saved coordinates and straight-line distance, not road travel distance.
It does not verify the reviewer's physical location or prevent false location input.

Tests cover exact boundaries, direct acceptance, query-filter bypass, custom and
invalid settings, no money side effects on rejection, and the Delhi/Bengaluru case.
