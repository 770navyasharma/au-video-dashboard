"""Fetch Pinot video watch time per-day (clean slice: excludes au-native-player).
Write video_id + video_title + watch_time to CDP_Daily tab."""
import os, json, datetime as dt
import requests
import gspread
from google.oauth2 import service_account
import config as C


def sheet_client():
    creds = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GCP_SERVICE_ACCOUNT_JSON"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return gspread.authorize(creds)


def pinot_query(sql):
    # Server-side 300s timeout (same as Navya sets in the Pinot console).
    # The broker was timing out on stage 0 at the default 60s on busy days
    # (e.g. 2026-11-01) with JSON_EXTRACT_SCALAR + GROUP BY on all events.
    r = requests.post(
        f"{C.PINOT_HOST}/sql",
        json={"sql": sql, "queryOptions": "timeoutMs=300000"},
        auth=(C.PINOT_USER, os.environ["PINOT_PASSWORD"]),
        timeout=320,  # client timeout must be > server timeout
    )
    r.raise_for_status()
    data = r.json()
    if data.get("exceptions"):
        raise RuntimeError(f"Pinot error: {data['exceptions']}")
    return data.get("resultTable", {}).get("rows", [])


def fetch_one_day(date_str):
    """App-only clean slice:
       - platform IN ('android', 'ios')  — strict app-only (top-level column)
       - videoProvider != 'au-native-player' — exclude buggy web player (defense in depth)
       - time_spent > 0 — skip zero-duration noise (pushes filter to DB, lighter)
    Time filter FIRST (per Pinot best practice: event_date_ist is the partition key).
    """
    sql = f"""
    SELECT
      video_id,
      JSON_EXTRACT_SCALAR(metadata, '$.videoTitle', 'STRING', '') AS video_title,
      SUM(time_spent) AS watch_time_seconds
    FROM events
    WHERE event_date_ist = '{date_str}'
      AND event_type = 'VIDEO_WATCH_TIME'
      AND platform IN ('android', 'ios')
      AND time_spent > 0
      AND video_id != 'null' AND video_id != ''
    GROUP BY video_id,
             JSON_EXTRACT_SCALAR(metadata, '$.videoTitle', 'STRING', '')
    LIMIT 100000
    """
    rows = pinot_query(sql)
    out = []
    for r in rows:
        vid = (r[0] or "").strip()
        title = (r[1] or "").strip()
        try:
            wt = int(r[2] or 0)
        except (ValueError, TypeError):
            wt = 0

        if not vid or vid == "null":
            continue
        if not title or title == "null":
            continue
        if wt <= 0:
            continue

        out.append([date_str, vid, title, wt])
    return out


def upsert(ws, dates_set, new_rows):
    """Delete rows for given dates, append new rows. Idempotent."""
    all_data = ws.get_all_values()
    kept = [all_data[0]] if all_data else [C.SHEET_HEADER]
    for row in all_data[1:]:
        if row and row[0] not in dates_set:
            kept.append(row)
    kept.extend(new_rows)
    ws.clear()
    ws.update(values=kept, range_name="A1")


def main():
    today = dt.date.today()
    window = [(today - dt.timedelta(days=d)).isoformat() for d in (2, 3)]
    if os.environ.get("BACKFILL_DATES"):
        window = [d.strip() for d in os.environ["BACKFILL_DATES"].split(",") if d.strip()]

    print(f"Pinot fetch window: {window}")

    sh = sheet_client().open_by_key(os.environ["SHEET_ID"])
    try:
        ws = sh.worksheet(C.CDP_TAB)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(C.CDP_TAB, 10000, 4)
        ws.append_row(C.SHEET_HEADER)

    # Overwrite the header if sheet already exists with old schema
    current_header = ws.row_values(1)
    if current_header != C.SHEET_HEADER:
        print(f"Updating header from {current_header} to {C.SHEET_HEADER}")
        ws.clear()
        ws.update(values=[C.SHEET_HEADER], range_name="A1")

    all_rows = []
    for d in window:
        rows = fetch_one_day(d)
        print(f"  {d}: {len(rows)} rows")
        all_rows.extend(rows)

    upsert(ws, set(window), all_rows)
    print(f"✅ CDP_Daily updated: {len(all_rows)} rows across {len(window)} days")


if __name__ == "__main__":
    main()
