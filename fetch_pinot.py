import os
import json
import time
from datetime import date, timedelta

import requests
import gspread
from google.oauth2 import service_account

import config as C


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


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


def pinot_query(sql):
    r = requests.post(
        f"{C.PINOT_HOST}/sql",
        json={"sql": sql, "queryOptions": "timeoutMs=600000"},
        auth=(C.PINOT_USER, os.environ["PINOT_PASSWORD"]),
        timeout=620,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("exceptions"):
        raise RuntimeError(f"Pinot error: {data['exceptions']}")
    return data.get("resultTable", {}).get("rows", [])


def build_sql(dates):
    """One query, finest grain (date × 7 dims). Unique-user count uses
       user_id for logged-in traffic and falls back to metadata.guestId for
       non-logged-in — gives us app-wide unique reach across both buckets.
       HLL keeps the 7-dim-groupby cheap (~1% approximation error)."""
    select_parts = ["event_date_ist"]
    for d in C.DIMENSIONS:
        select_parts.append(f"{d['cdp_expr']} AS {d['field']}")

    group_parts = ["event_date_ist"] + [d["cdp_expr"] for d in C.DIMENSIONS]

    # Prefer user_id; fall back to guestId from metadata when user_id is
    # empty / null (non-logged-in sessions).
    user_expr = (
        "CASE "
        "WHEN user_id IS NOT NULL AND user_id != '' AND user_id != 'null' "
        "THEN user_id "
        "ELSE JSON_EXTRACT_SCALAR(metadata, '$.guestId', 'STRING', '') "
        "END"
    )

    select_clause = (
        ", ".join(select_parts)
        + f", DISTINCTCOUNTHLL({user_expr}) AS unique_users"
        + ", SUM(time_spent) AS watch_time_seconds"
    )
    group_clause = ", ".join(group_parts)
    dates_list = ", ".join(f"'{d}'" for d in dates)

    return (
        f"SELECT {select_clause} "
        f"FROM events "
        f"WHERE event_type = 'VIDEO_WATCH_TIME' "
        f"AND event_date_ist IN ({dates_list}) "
        f"AND platform IN ('android', 'ios') "
        f"AND video_id != 'null' AND video_id != '' "
        f"AND JSON_EXTRACT_SCALAR(metadata, '$.videoProvider', 'STRING', '') != 'au-native-player' "
        f"GROUP BY {group_clause} "
        f"LIMIT 1000000"
    )


def fetch_window(dates):
    sql = build_sql(dates)
    rows = pinot_query(sql)
    result = []
    # Row shape: [date, dim1..dim7, unique_users, watch_time_seconds]
    for r in rows:
        wt = int(r[-1] or 0)
        users = int(r[-2] or 0)
        if wt <= 0:
            continue
        date_val = r[0]
        dims = list(r[1:-2])  # 7 dim values
        if not dims[0]:
            continue
        dims = [v if v else "(not set)" for v in dims]
        result.append([date_val] + dims + [users, wt])
    return result


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

    backfill = os.environ.get("BACKFILL_DATES", "").strip()
    if backfill:
        dates = [d.strip() for d in backfill.split(",") if d.strip()]
    else:
        today = date.today()
        dates = [
            (today - timedelta(days=i + C.FETCH_LAG_DAYS)).strftime("%Y-%m-%d")
            for i in range(2)
        ]

    print(f"Pinot fetch window: {dates[0]} -> {dates[-1]} ({len(dates)} days)")
    print(f"Dimensions: {[d['field'] for d in C.DIMENSIONS]}")
    print(f"Metrics: unique_users (HLL), watch_time_seconds\n")

    ws = get_or_create_ws(ss, C.CDP_TAB, C.SHEET_HEADER)

    t0 = time.time()
    rows = fetch_window(dates)
    print(f"  Pinot query: {len(rows)} rows in {time.time()-t0:.1f}s")

    upsert(ws, set(dates), rows)
    print(f"\n✅ {C.CDP_TAB} updated: {len(rows)} rows across {len(dates)} days")


if __name__ == "__main__":
    main()
