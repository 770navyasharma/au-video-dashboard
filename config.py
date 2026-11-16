# GA4
GA_PROPERTY_ID = "153697708"
GA_METRIC_WATCH_TIME = "watch_time_seconds"
GA_EVENT_NAME = "video_watch_time"
GA_EXCLUDE_STREAM = "Amarujala Web"   # exclude web stream to match app-only slice

# Pinot CDP
PINOT_HOST = "http://46.62.191.123:9000"
PINOT_USER = "analyst"

# how many days behind "today" to start fetching (GA + CDP both have landing lag)
FETCH_LAG_DAYS = 2

# ---------------------------------------------------------------------------
# Breakdowns — each one gets its own GA sheet + CDP sheet, same schema shape:
#   ["date"] + dims + ["watch_time_seconds"]
#
# `ga_dims` are GA4 custom-dimension names (exact, as registered in GA4).
# `cdp_cols` are (sql_expression, output_alias) pairs; the alias becomes the
#   sheet column name AND is what GROUP BY uses.
# ---------------------------------------------------------------------------
BREAKDOWNS = [
    {
        "name": "video",
        "ga_tab": "GA_Daily",
        "cdp_tab": "CDP_Daily",
        "dims": ["video_id", "video_title"],
        "ga_dims": ["video_id", "video_title"],
        "cdp_cols": [
            ("video_id", "video_id"),
            ("JSON_EXTRACT_SCALAR(metadata, '$.videoTitle', 'STRING', '')", "video_title"),
        ],
    },
    {
        "name": "unit",
        "ga_tab": "GA_Unit",
        "cdp_tab": "CDP_Unit",
        "dims": ["unit_name"],
        "ga_dims": ["unit_name"],
        "cdp_cols": [
            ("JSON_EXTRACT_SCALAR(metadata, '$.unitName', 'STRING', '')", "unit_name"),
        ],
    },
    {
        "name": "category",
        "ga_tab": "GA_Category",
        "cdp_tab": "CDP_Category",
        "dims": ["parent_category", "child_category"],
        "ga_dims": ["parent_category", "child_category"],
        "cdp_cols": [
            ("JSON_EXTRACT_SCALAR(metadata, '$.category', 'STRING', '')", "parent_category"),
            ("JSON_EXTRACT_SCALAR(metadata, '$.subCategory', 'STRING', '')", "child_category"),
        ],
    },
    {
        "name": "city",
        "ga_tab": "GA_City",
        "cdp_tab": "CDP_City",
        "dims": ["location_city"],
        "ga_dims": ["location_city"],
        "cdp_cols": [
            ("JSON_EXTRACT_SCALAR(metadata, '$.locationCity', 'STRING', '')", "location_city"),
        ],
    },
    {
        "name": "state",
        "ga_tab": "GA_State",
        "cdp_tab": "CDP_State",
        "dims": ["location_state"],
        "ga_dims": ["location_state"],
        "cdp_cols": [
            ("JSON_EXTRACT_SCALAR(metadata, '$.locationState', 'STRING', '')", "location_state"),
        ],
    },
]


def sheet_header(breakdown):
    return ["date"] + breakdown["dims"] + ["watch_time_seconds"]
