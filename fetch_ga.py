"""Fetch GA4 video watch time per-day, write to GA_Daily tab. Fails hard on sampling."""
import os, json, datetime as dt
import gspread
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest, DateRange, Dimension, Metric, Filter, FilterExpression
)
import config as C


def _creds(scopes):
    return service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GCP_SERVICE_ACCOUNT_JSON"]),
        scopes=scopes,
    )


def ga_client():
    return BetaAnalyticsDataClient(
        credentials=_creds(["https://www.googleapis.com/auth/analytics.readonly"])
    )


def sheet_client():
    return gspread.authorize(_creds(["https://www.googleapis.com/auth/spreadsheets"]))


def fetch_one_day(client, date_str):
    """Query GA4 for one date. Returns list of [date, video_id, title, author, watch_time]."""
    req = RunReportRequest(
        property=f"properties/{C.GA_PROPERTY_ID}",
        date_ranges=[DateRange(start_date=date_str, end_date=date_str)],
        dimensions=[
            Dimension(name=f"customEvent:{C.GA_DIM_VIDEO_ID}"),
            Dimension(name=f"customEvent:{C.GA_DIM_VIDEO_TITLE}"),
            Dimension(name=f"customEvent:{C.GA_DIM_AUTHOR}"),
        ],
        metrics=[Metric(name=f"customEvent:{C.GA_METRIC_WATCH_TIME}")],
        dimension_filter=FilterExpression(filter=Filter(
            field_name="eventName",
            string_filter=Filter.StringFilter(value=C.GA_EVENT_NAME),
        )),
        limit=100000,
    )
    resp = client.run_report(req)

    # Sampling check — FAIL hard if sampled (Navya's rule: NO sampling allowed)
    for sm in (resp.metadata.sampling_metadatas or []):
        if sm.samples_read_count and sm.samples_read_count < sm.sampling_space_size:
            raise RuntimeError(
                f"🚨 SAMPLED DATA on {date_str}: "
                f"{sm.samples_read_count}/{sm.sampling_space_size} — aborting."
            )

    rows = []
    for r in resp.rows:
        vid = r.dimension_values[0].value or ""
        title = r.dimension_values[1].value or ""
        author = r.dimension_values[2].value or ""
        try:
            wt = int(float(r.metric_values[0].value or 0))
        except (ValueError, TypeError):
            wt = 0
        if not vid or vid == "(not set)":
            continue
        rows.append([date_str, vid, title, author, wt])
    return rows


def upsert(ws, dates_set, new_rows):
    """Delete rows for given dates, append new rows. Idempotent."""
    all_data = ws.get_all_values()
    header = ["date", "video_id", "video_title", "author", "watch_time_seconds"]
    kept = [all_data[0]] if all_data else [header]
    for row in all_data[1:]:
        if row and row[0] not in dates_set:
            kept.append(row)
    kept.extend(new_rows)
    ws.clear()
    ws.update(values=kept, range_name="A1")


def main():
    # Default: last 2 complete days (lag of 2 — day-1 may still be incomplete in GA)
    today = dt.date.today()
    window = [(today - dt.timedelta(days=d)).isoformat() for d in (2, 3)]

    # Backfill mode: override via env (used by manual workflow_dispatch)
    if os.environ.get("BACKFILL_DATES"):
        window = [d.strip() for d in os.environ["BACKFILL_DATES"].split(",") if d.strip()]

    print(f"GA fetch window: {window}")

    ga = ga_client()
    sh = sheet_client().open_by_key(os.environ["SHEET_ID"])
    try:
        ws = sh.worksheet(C.GA_TAB)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(C.GA_TAB, 10000, 5)
        ws.append_row(["date", "video_id", "video_title", "author", "watch_time_seconds"])

    all_rows = []
    for d in window:
        rows = fetch_one_day(ga, d)
        print(f"  {d}: {len(rows)} rows")
        all_rows.extend(rows)

    upsert(ws, set(window), all_rows)
    print(f"✅ GA_Daily updated: {len(all_rows)} rows across {len(window)} days")


if __name__ == "__main__":
    main()
