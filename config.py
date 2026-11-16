# ============ Amar Ujala Video Dashboard config ============
# Only 3 fields tracked: video_id, video_title, watch_time_seconds
# Author dropped — too many "(not set)" / null values in source data

GA_PROPERTY_ID = "153697708"           # main Amarujala GA4 property
PINOT_HOST = "http://46.62.191.123:9000"
PINOT_USER = "analyst"                 # Navya's Pinot user

# GA4 custom dimension/metric API names (confirmed from GA4 Admin → Custom definitions)
GA_DIM_VIDEO_ID = "video_id"
GA_DIM_VIDEO_TITLE = "video_title"
GA_METRIC_WATCH_TIME = "watch_time_seconds"
GA_EVENT_NAME = "video_watch_time"     # lowercase in GA4
GA_EXCLUDE_STREAM = "Amarujala Web"    # exclude web stream → app-only (matches GA Exploration)

# Sheet tab names
GA_TAB = "GA_Daily"
CDP_TAB = "CDP_Daily"

# 4-column schema (no author)
SHEET_HEADER = ["date", "video_id", "video_title", "watch_time_seconds"]
