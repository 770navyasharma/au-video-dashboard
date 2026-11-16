"""Fetch Pinot video watch time per-day (clean slice: excludes au-native-player).
Write to CDP_Daily tab."""
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
    r = requests.post(
        f"{C.PINOT_HOST}/sql",
        json={"sql": sql, "queryOptions": "useMultistageEngine=true"},
        auth=(C.PINOT_USER, os.environ["PINOT_PASSWORD"]),
        timeout=180,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("exceptions"):
        raise RuntimeError(f"Pinot error: {data['exceptions']}")
    return data.get("resultTable", {}).get("rows", [])


def fetch_one_day(date_str):
    """Clean-slice: native app traffic (au_video + youtube + native), excludes au-native-player."""
    sql = f"""
    SELECT
      video_id,
      JSON_EXTRACT_SCALAR(metadata, '$.videoTitle', 'STRING', '') AS video_title,
      story_author_name,
      SUM(time_spent) AS watch_time_seconds
    FROM events
    WHERE event_type = 'VIDEO_WATCH_TIME'
      AND event_date_ist = '{date_str}'
      AND video_id != 'null' AND video_id != ''
      AND JSON_EXTRACT_SCALAR(metadata, '$.videoProvider', 'STRING', '') != 'au-native-player'
    GROUP BY video_id,
             JSON_EXTRACT_SCALAR(metadata, '$.videoTitle', 'STRING', ''),
             story_author_name
    LIMIT 100000
    """
    rows = pinot_query(sql)
    out = []
    for r in rows:
        vid = r[0] or ""
        title = r[1] or ""
        author = r[2] or ""
        try:
            wt = int(r[3] or 0)
        except (ValueError, TypeError):
            wt = 0
        if not vid or vid == "null":
            continue
        if author == "null":
            author = ""
        out.append([date_str, vid, title, author, wt])
    return out


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
    today = dt.date.today()
    window = [(today - dt.timedelta(days=d)).isoformat() for d in (2, 3)]

    if os.environ.get("BACKFILL_DATES"):
        window = [d.strip() for d in os.environ["BACKFILL_DATES"].split(",") if d.strip()]

    print(f"Pinot fetch window: {window}")

    sh = sheet_client().open_by_key(os.environ["SHEET_ID"])
    try:
        ws = sh.worksheet(C.CDP_TAB)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(C.CDP_TAB, 10000, 5)
        ws.append_row(["date", "video_id", "video_title", "author", "watch_time_seconds"])

    all_rows = []
    for d in window:
        rows = fetch_one_day(d)
        print(f"  {d}: {len(rows)} rows")
        all_rows.extend(rows)

    upsert(ws, set(window), all_rows)
    print(f"✅ CDP_Daily updated: {len(all_rows)} rows across {len(window)} days")


if __name__ == "__main__":
    main()
