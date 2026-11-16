# ============ Amar Ujala Video Dashboard config ============
# These values match Navya's GA4 Custom Definitions (verified 2026-11-16).
# If you ever rename a dimension/metric in GA4, change it here only.

GA_PROPERTY_ID = "153697708"           # main Amarujala GA4 property
PINOT_HOST = "http://46.62.191.123:9000"
PINOT_USER = "admin"                   # change if your Pinot user is different

# GA4 custom dimension/metric API names (Admin → Custom definitions → Parameter name column)
GA_DIM_VIDEO_ID = "video_id"
GA_DIM_VIDEO_TITLE = "video_title"
GA_DIM_AUTHOR = "story_author"         # confirmed from GA4 screenshot
GA_METRIC_WATCH_TIME = "watch_time_seconds"
GA_EVENT_NAME = "video_watch_time"     # lowercase in GA4

# Sheet tab names (don't change unless you rename the tabs in the Sheet too)
GA_TAB = "GA_Daily"
CDP_TAB = "CDP_Daily"
