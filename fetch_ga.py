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


SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]


def _creds():
    info = json.loads(os.environ["GCP_SERVICE_ACCOUNT_JSON"])
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)


def get_or_create_ws(ss, tab_name, header):
    try:
        ws = ss.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        print(f"  Creating new sheet tab: {tab_name}")
        ws = ss.add_worksheet(title=tab_name, rows=50000, cols=20)
        ws.append_row(header)
        return ws
    first_row = ws.row_values(1)
    if first_row != header:
        print(f"  Migrating header of {tab_name}: {first_row} -> {header}")
        ws.clear()
        ws.append_row(header)
    return ws


def fetch_one_day(client, date_str):
    """Pull one day's data at finest grain: 7 dims × video_id, with
       (totalUsers, watch_time_seconds) as the two metrics."""
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

    # totalUsers is BUILT-IN, no `customEvent:` prefix.
    # watch_time_seconds is a custom event metric, needs the prefix.
    req = RunReportRequest(
        property=f"properties/{C.GA_PROPERTY_ID}",
        dimensions=[Dimension(name=f"customEvent:{d['ga_dim']}") for d in C.DIMENSIONS],
        metrics=[
            Metric(name=C.GA_METRIC_USERS),
            Metric(name=f"customEvent:{C.GA_METRIC_WATCH_TIME}"),
        ],
        date_ranges=[DateRange(start_date=date_str, end_date=date_str)],
        dimension_filter=combined,
        limit=100000,
    )
    resp = client.run_report(req)

    if resp.metadata.sampling_metadatas:
        raise RuntimeError(f"GA sampling detected on {date_str} — refusing sampled data")

    if resp.row_count and resp.row_count > len(resp.rows):
        raise RuntimeError(
            f"GA truncation on {date_str}: {resp.row_count} rows available, got {len(resp.rows)}. Reduce dims or add paging."
        )

    rows = []
    for r in resp.rows:
        dim_values = [d.value or "" for d in r.dimension_values]
        users = int(r.metric_values[0].value or 0)
        wt = int(r.metric_values[1].value or 0)
        if wt <= 0:
            continue
        if not dim_values[0] or dim_values[0] == "(not set)":
            continue
        dim_values = [v if v else "(not set)" for v in dim_values]
        rows.append([date_str] + dim_values + [users, wt])
    return rows


def upsert(ws, dates_set, new_rows):
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

    print(f"GA fetch window: {dates[0]} -> {dates[-1]} ({len(dates)} days)")
    print(f"Dimensions: {[d['ga_dim'] for d in C.DIMENSIONS]}")
    print(f"Metrics: [{C.GA_METRIC_USERS}, {C.GA_METRIC_WATCH_TIME}]\n")

    ws = get_or_create_ws(ss, C.GA_TAB, C.SHEET_HEADER)

    all_rows = []
    for d in dates:
        rows = fetch_one_day(client, d)
        print(f"  {d}: {len(rows)} rows")
        all_rows.extend(rows)

    upsert(ws, set(dates), all_rows)
    print(f"\n✅ {C.GA_TAB} updated: {len(all_rows)} rows across {len(dates)} days")


if __name__ == "__main__":
    main()
