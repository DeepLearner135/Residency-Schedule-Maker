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

def generate_composite_calendar(
    start_date, end_date, 
    residents_df, attendings_df, blocks_df, block_assignments, 
    vacations_df, inpatient_df, coverage_df, call_df
):
    import re
    residents = residents_df["Name"].tolist() if not residents_df.empty else []
    
    # Pre-process DataFrames into fast lookup dictionaries
    vacation_lookup = {}
    if vacations_df is not None and not vacations_df.empty:
        for _, row in vacations_df.iterrows():
            r = row["Resident"]
            current = pd.to_datetime(row["Start Date"]).date()
            end = pd.to_datetime(row["End Date"]).date()
            while current <= end:
                vacation_lookup.setdefault(current, set()).add(r)
                current += timedelta(days=1)
                
    inpatient_lookup = {}
    if inpatient_df is not None and not inpatient_df.empty:
         for _, row in inpatient_df.iterrows():
             d = pd.to_datetime(row["Date"]).date()
             r = row.get("Resident")
             if r: inpatient_lookup.setdefault(d, set()).add(r)

    coverage_lookup = {}
    if coverage_df is not None and not coverage_df.empty:
         for _, row in coverage_df.iterrows():
             d = pd.to_datetime(row["Date"]).date()
             r = row.get("Covering Resident")
             att = row.get("Attending Needed")
             if r and att:
                 coverage_lookup.setdefault(d, {})[r] = f"Covering {att}"

    call_lookup = {}
    if call_df is not None and not call_df.empty:
        for _, row in call_df.iterrows():
            r = row.get("Resident")
            if pd.notna(r) and r != "Unassigned":
                current = pd.to_datetime(row["Week Start"]).date()
                end = pd.to_datetime(row["Week End"]).date()
                while current <= end:
                    call_lookup.setdefault(current, set()).add(r)
                    current += timedelta(days=1)
    
    block_starts = {}
    if blocks_df is not None and not blocks_df.empty:
        for _, row in blocks_df.iterrows():
            d = pd.to_datetime(row["Start Date"]).date()
            block_starts[d] = row
            
    # Cache attending clinic days
    attending_clinics = {}
    if attendings_df is not None and not attendings_df.empty:
        for _, row in attendings_df.iterrows():
            name = row["Name"]
            days_str = str(row.get("Clinic Days", ""))
            attending_clinics[name] = [d.strip() for d in days_str.split(",") if d.strip()]
            
    current_assignments = {r: None for r in residents}
            
    # Build the rows
    current_date = start_date
    rows = []
    
    while current_date <= end_date:
        if current_date in block_starts:
            b_row = block_starts[current_date]
            b_name = b_row["Block Name"]
            
            row_data = {
                "Date": f"--- {b_name} ---",
                "Day": ""
            }
            for r in residents:
                assignment = ""
                if block_assignments is not None and not block_assignments.empty and b_name in block_assignments.columns and r in block_assignments.index:
                    val = block_assignments.loc[r, b_name]
                    assignment = val if pd.notna(val) else "Unassigned"
                row_data[r] = assignment
                current_assignments[r] = assignment
            rows.append(row_data)
            
        day_of_week = current_date.strftime("%A")
        row_data = {
            "Date": current_date.strftime("%Y-%m-%d"),
            "Day": day_of_week
        }
        for r in residents:
            cell_text = []
            
            assignment = current_assignments.get(r)
            if assignment and assignment != "Unassigned" and "Satellite" not in assignment and "Elective" not in assignment and "Research" not in assignment:
                bases = [part.strip() for part in re.split(r'[/&]', assignment) if part.strip()]
                for base_att in bases:
                    if base_att in attending_clinics:
                        if any(day_name in attending_clinics[base_att] for day_name in [day_of_week]):
                            cell_text.append("Clinic")
                            break
                            
            if current_date in vacation_lookup and r in vacation_lookup[current_date]:
                cell_text.append("Vacation")
            else:
                if current_date in coverage_lookup and r in coverage_lookup[current_date]:
                    cell_text.append(coverage_lookup[current_date][r])
                if current_date in inpatient_lookup and r in inpatient_lookup[current_date]:
                    cell_text.append("Inpatient")
                    
            if current_date in call_lookup and r in call_lookup[current_date]:
                cell_text.append("(Call)")
                
            row_data[r] = ", ".join(cell_text) if cell_text else ""
            
        rows.append(row_data)
        current_date += timedelta(days=1)
        
    return pd.DataFrame(rows)
