# GA4
GA_PROPERTY_ID = "153697708"
GA_METRIC_WATCH_TIME = "watch_time_seconds"      # custom event-scoped metric
GA_METRIC_USERS = "totalUsers"                   # built-in GA4 metric (no customEvent: prefix)
GA_EVENT_NAME = "video_watch_time"
GA_EXCLUDE_STREAM = "Amarujala Web"

# Pinot CDP
PINOT_HOST = "http://46.62.191.123:9000"
PINOT_USER = "analyst"

FETCH_LAG_DAYS = 2

# The 7 dimensions the dashboard lets you toggle + aggregate by. Each row
# in the sheet lives at the finest grain (date × all 7 dims); the dashboard
# JS re-aggregates client-side whenever a toggle flips.
#
#   ga_dim   = GA4 custom-dimension name (bare — fetch_ga adds the
#              `customEvent:` prefix at API-call time)
#   cdp_expr = Pinot SQL expression. video_id is a top-level column; rest
#              are JSON_EXTRACT_SCALAR'd out of the metadata blob.
DIMENSIONS = [
    {"field": "video_id",        "label": "Video ID",         "ga_dim": "video_id",
     "cdp_expr": "video_id"},
    {"field": "video_title",     "label": "Video Title",      "ga_dim": "video_title",
     "cdp_expr": "JSON_EXTRACT_SCALAR(metadata, '$.videoTitle', 'STRING', '')"},
    {"field": "unit_name",       "label": "Unit Name",        "ga_dim": "unit_name",
     "cdp_expr": "JSON_EXTRACT_SCALAR(metadata, '$.unitName', 'STRING', '')"},
    {"field": "parent_category", "label": "Parent Category",  "ga_dim": "parent_category",
     "cdp_expr": "JSON_EXTRACT_SCALAR(metadata, '$.category', 'STRING', '')"},
    {"field": "child_category",  "label": "Child Category",   "ga_dim": "child_category",
     "cdp_expr": "JSON_EXTRACT_SCALAR(metadata, '$.subCategory', 'STRING', '')"},
    {"field": "location_city",   "label": "Location City",    "ga_dim": "location_city",
     "cdp_expr": "JSON_EXTRACT_SCALAR(metadata, '$.locationCity', 'STRING', '')"},
    {"field": "location_state",  "label": "Location State",   "ga_dim": "location_state",
     "cdp_expr": "JSON_EXTRACT_SCALAR(metadata, '$.locationState', 'STRING', '')"},
]

GA_TAB = "GA_All"
CDP_TAB = "CDP_All"

# unique_users comes BEFORE watch_time_seconds in the sheet so the metric
# is always the last column (dashboard assumes last col = watch_time).
SHEET_HEADER = (
    ["date"]
    + [d["field"] for d in DIMENSIONS]
    + ["unique_users", "watch_time_seconds"]
)
