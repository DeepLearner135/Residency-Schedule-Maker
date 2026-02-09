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
        values="Resident",
        aggfunc=lambda x: ", ".join(x.unique())
    )
    
    # Reorder columns
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    existing_days = [d for d in days if d in pivot.columns]
    pivot = pivot[existing_days]
    
    # Reset index to make Week Start a column
    pivot = pivot.reset_index()
    pivot["Week Start"] = pivot["Week Start"].dt.strftime('%Y-%m-%d')
    
    return pivot
