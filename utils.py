import pandas as pd
from datetime import date, timedelta

def create_inpatient_calendar_df(schedule_df: pd.DataFrame) -> pd.DataFrame:
    """
    Transforms the daily Inpatient Schedule into a Weekly/Monthly Calendar view.
    Format:
    Week Start | Mon | Tue | Wed | Thu | Fri
    """
    if schedule_df.empty:
        return pd.DataFrame()
        
    df = schedule_df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date")
    
    # Add Week Start
    # Assuming Week Start is Monday
    df["Week Start"] = df["Date"] - pd.to_timedelta(df["Date"].dt.dayofweek, unit='D')
    
    # Pivot?
    # We want rows to be "Resident" or just "Assignment"?
    # Actually, usually Inpatient Schedule matches Residents to Days.
    # User said "each row (or group of rows) has a Monday to Friday".
    # So Columns: Mon, Tue, Wed, Thu, Fri.
    # Rows: Week 1, Week 2...
    # And inside the cell: Resident Name(s).
    
    # Pivot
    pivot = df.pivot_table(
        index="Week Start",
        columns="Day", # Mon, Tue...
        values="Date", # We need both Date and Resident
        aggfunc=lambda x: "TEMP" # Placeholder
    )
    
    # Actually, pivot_table is tricky if we want combined string "Date - Resident"
    # Let's iterate.
    week_starts = sorted(df["Week Start"].unique())
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    
    cal_rows = []
    
    for ws in week_starts:
        week_data = df[df["Week Start"] == ws]
        row = {"Week Start": ws.strftime('%Y-%m-%d')}
        
        for d_name in days_order:
            day_data = week_data[week_data["Day"] == d_name]
            if not day_data.empty:
                # Combine Date and Resident
                entries = []
                for _, r in day_data.iterrows():
                    d_str = r["Date"].strftime("%m/%d")
                    res = r["Resident"]
                    entries.append(f"{d_str}\n{res}")
                row[d_name] = "\n".join(entries)
            else:
                row[d_name] = ""
        cal_rows.append(row)
        
    return pd.DataFrame(cal_rows, columns=["Week Start"] + days_order)
