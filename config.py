# GA4
GA_PROPERTY_ID = "153697708"
GA_METRIC_WATCH_TIME = "watch_time_seconds"
GA_EVENT_NAME = "video_watch_time"
GA_EXCLUDE_STREAM = "Amarujala Web"

# Pinot CDP
PINOT_HOST = "http://46.62.191.123:9000"
PINOT_USER = "analyst"

# how many days behind "today" to start fetching
FETCH_LAG_DAYS = 2

# The 7 dimensions we pull per event. The dashboard lets the user toggle
# which of these to show + aggregate by — client-side re-aggregation drives
# all the "unit wise / city wise / combined" views, so a single source of
# truth per side (GA + CDP) is enough.
#
#   ga_dim  = GA4 custom-dimension name (bare — fetch_ga adds the
#             `customEvent:` prefix at API-call time)
#   cdp_expr = Pinot SQL expression. video_id is a top-level column; the
#              rest are JSON_EXTRACT_SCALAR'd from the metadata blob.
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

SHEET_HEADER = ["date"] + [d["field"] for d in DIMENSIONS] + ["watch_time_seconds"]
