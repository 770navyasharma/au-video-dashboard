"""One-off cleanup: delete the 10 old breakdown tabs now that GA_All + CDP_All
   are the source of truth. Safe to run multiple times — skips tabs that
   don't exist. Never touches GA_All or CDP_All."""

import os
import json
import gspread
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

OLD_TABS = [
    "GA_Daily", "CDP_Daily",
    "GA_Unit", "CDP_Unit",
    "GA_Category", "CDP_Category",
    "GA_City", "CDP_City",
    "GA_State", "CDP_State",
]

PROTECTED = {"GA_All", "CDP_All"}  # never delete these


def main():
    info = json.loads(os.environ["GCP_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(os.environ["SHEET_ID"])

    existing = {ws.title for ws in ss.worksheets()}
    print(f"Found tabs: {sorted(existing)}\n")

    for tab in OLD_TABS:
        if tab in PROTECTED:
            print(f"  ⚠  SKIP {tab} (protected)")
            continue
        if tab not in existing:
            print(f"  -  skip {tab} (doesn't exist)")
            continue
        ws = ss.worksheet(tab)
        ss.del_worksheet(ws)
        print(f"  🗑  deleted {tab}")

    remaining = {ws.title for ws in ss.worksheets()}
    print(f"\n✅ Remaining tabs: {sorted(remaining)}")


if __name__ == "__main__":
    main()
