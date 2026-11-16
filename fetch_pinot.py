import os
import json
from datetime import date, timedelta

import requests
import gspread
from google.oauth2 import service_account

import config as C


def _creds():
    info = json.loads(os.environ["GCP_SERVICE_ACCOUNT_JSON"])
    return service_account.Credentials.from_service_account_info(info)


def get_or_create_ws(ss, tab_name, header):
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


def pinot_query(sql):
    r = requests.post(
        f"{C.PINOT_HOST}/sql",
        json={"sql": sql, "queryOptions": "timeoutMs=300000"},
        auth=(C.PINOT_USER, os.environ["PINOT_PASSWORD"]),
        timeout=320,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("exceptions"):
        raise RuntimeError(f"Pinot error: {data['exceptions']}")
    return data.get("resultTable", {}).get("rows", [])


def build_sql(date_str, breakdown):
    select_parts = [f"{expr} AS {alias}" for expr, alias in breakdown["cdp_cols"]]
    group_parts = [expr for expr, _ in breakdown["cdp_cols"]]

    select_clause = ", ".join(select_parts) + ", SUM(time_spent) AS watch_time_seconds"
    group_clause = ", ".join(group_parts)

    # Video breakdown keeps the video_id tightness filter;
    # other breakdowns let (not set) rows through as a real bucket.
    extra = ""
    if breakdown["name"] == "video":
        extra = "AND video_id != 'null' AND video_id != '' "

    return (
        f"SELECT {select_clause} "
        f"FROM events "
        f"WHERE event_type = 'VIDEO_WATCH_TIME' "
        f"AND event_date_ist = '{date_str}' "
        f"AND platform IN ('android', 'ios') "
        f"AND JSON_EXTRACT_SCALAR(metadata, '$.videoProvider', 'STRING', '') != 'au-native-player' "
        f"{extra}"
        f"GROUP BY {group_clause} "
        f"LIMIT 100000"
    )


def fetch_one_day(date_str, breakdown):
    sql = build_sql(date_str, breakdown)
    rows = pinot_query(sql)
    result = []
    for r in rows:
        wt = int(r[-1] or 0)
        if wt <= 0:
            continue
        dims = list(r[:-1])
        if breakdown["name"] == "video":
            if not dims[0] or not dims[1]:
                continue
        # Normalize empty-string dims to "(not set)" so GA and CDP match visually
        dims = [v if v else "(not set)" for v in dims]
        result.append([date_str] + dims + [wt])
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

    print(f"Pinot fetch window: {dates}\n")

    for breakdown in C.BREAKDOWNS:
        print(f"--- Pinot breakdown: {breakdown['name']} -> {breakdown['cdp_tab']} ---")
        header = C.sheet_header(breakdown)
        ws = get_or_create_ws(ss, breakdown["cdp_tab"], header)

        all_rows = []
        for d in dates:
            rows = fetch_one_day(d, breakdown)
            print(f"  {d}: {len(rows)} rows")
            all_rows.extend(rows)

        upsert(ws, set(dates), all_rows)
        print(f"  ✅ {breakdown['cdp_tab']} updated: {len(all_rows)} rows across {len(dates)} days\n")


if __name__ == "__main__":
    main()
