import os
import json
from datetime import date, timedelta

import gspread
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest, DateRange, Dimension, Metric,
    FilterExpression, FilterExpressionList, Filter,
)

import config as C


def _creds():
    info = json.loads(os.environ["GCP_SERVICE_ACCOUNT_JSON"])
    return service_account.Credentials.from_service_account_info(info)


def get_or_create_ws(ss, tab_name, header):
    """Open the sheet tab, or create it with the right header if missing.
       If the existing header is stale, clear and rewrite."""
    try:
        ws = ss.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        print(f"  Creating new sheet tab: {tab_name}")
        ws = ss.add_worksheet(title=tab_name, rows=10000, cols=20)
        ws.append_row(header)
        return ws
    first_row = ws.row_values(1)
    if first_row != header:
        print(f"  Migrating header of {tab_name}: {first_row} -> {header}")
        ws.clear()
        ws.append_row(header)
    return ws


def fetch_one_day(client, date_str, breakdown):
    """Run one GA4 report for one day + one breakdown. Returns list of rows."""
    event_filter = FilterExpression(
        filter=Filter(
            field_name="eventName",
            string_filter=Filter.StringFilter(value=C.GA_EVENT_NAME),
        )
    )
    stream_filter = FilterExpression(
        not_expression=FilterExpression(
            filter=Filter(
                field_name="streamName",
                string_filter=Filter.StringFilter(
                    value=C.GA_EXCLUDE_STREAM,
                    match_type=Filter.StringFilter.MatchType.EXACT,
                ),
            )
        )
    )
    combined = FilterExpression(
        and_group=FilterExpressionList(expressions=[event_filter, stream_filter])
    )

    req = RunReportRequest(
        property=f"properties/{C.GA_PROPERTY_ID}",
        dimensions=[Dimension(name=d) for d in breakdown["ga_dims"]],
        metrics=[Metric(name=C.GA_METRIC_WATCH_TIME)],
        date_ranges=[DateRange(start_date=date_str, end_date=date_str)],
        dimension_filter=combined,
        limit=100000,
    )
    resp = client.run_report(req)

    if resp.metadata.sampling_metadatas:
        raise RuntimeError(
            f"GA sampling detected on {date_str} for breakdown '{breakdown['name']}' — refusing sampled data"
        )

    rows = []
    for r in resp.rows:
        dim_values = [d.value for d in r.dimension_values]
        wt = int(r.metric_values[0].value or 0)
        if wt <= 0:
            continue
        # Video breakdown: drop empty / (not set) video_id or title (noise).
        # Other breakdowns: keep "(not set)" rows — it's a real bucket.
        if breakdown["name"] == "video":
            if not dim_values[0] or dim_values[0] == "(not set)":
                continue
            if not dim_values[1] or dim_values[1] == "(not set)":
                continue
        rows.append([date_str] + dim_values + [wt])
    return rows


def upsert(ws, dates_set, new_rows):
    """Keep rows whose date is NOT in dates_set, then add new_rows. Idempotent."""
    existing = ws.get_all_values()
    header = existing[0] if existing else None
    kept = [row for row in existing[1:] if row and row[0] not in dates_set]
    kept.extend(new_rows)
    ws.clear()
    ws.append_row(header)
    if kept:
        ws.append_rows(kept, value_input_option="RAW")


def main():
    creds = _creds()
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(os.environ["SHEET_ID"])
    client = BetaAnalyticsDataClient(credentials=creds)

    backfill = os.environ.get("BACKFILL_DATES", "").strip()
    if backfill:
        dates = [d.strip() for d in backfill.split(",") if d.strip()]
    else:
        today = date.today()
        dates = [
            (today - timedelta(days=i + C.FETCH_LAG_DAYS)).strftime("%Y-%m-%d")
            for i in range(2)
        ]

    print(f"GA fetch window: {dates}\n")

    for breakdown in C.BREAKDOWNS:
        print(f"--- GA breakdown: {breakdown['name']} -> {breakdown['ga_tab']} ---")
        header = C.sheet_header(breakdown)
        ws = get_or_create_ws(ss, breakdown["ga_tab"], header)

        all_rows = []
        for d in dates:
            rows = fetch_one_day(client, d, breakdown)
            print(f"  {d}: {len(rows)} rows")
            all_rows.extend(rows)

        upsert(ws, set(dates), all_rows)
        print(f"  ✅ {breakdown['ga_tab']} updated: {len(all_rows)} rows across {len(dates)} days\n")


if __name__ == "__main__":
    main()
