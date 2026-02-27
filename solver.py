from ortools.sat.python import cp_model
from typing import List, Dict, Any, Tuple, Optional
from datetime import date, timedelta
import pandas as pd

class ScheduleSolver:
    def __init__(self, residents_df: pd.DataFrame, attendings_df: pd.DataFrame, blocks_df: pd.DataFrame, assignments_df: pd.DataFrame, vacations_df: pd.DataFrame, start_date: date, end_date: date, inpatient_df: pd.DataFrame = None, coverage_df: pd.DataFrame = None):
        self.residents_df = residents_df
        self.attendings_df = attendings_df
        self.blocks_df = blocks_df
        self.assignments_df = assignments_df # Rows: Residents, Cols: Block Names
        self.vacations_df = vacations_df
        self.inpatient_df = inpatient_df if inpatient_df is not None else pd.DataFrame()
        self.coverage_df = coverage_df if coverage_df is not None else pd.DataFrame()
        self.start_date = start_date
        self.end_date = end_date
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()

    def _generate_weeks(self) -> List[Tuple[date, date]]:
        """Generates Monday-Sunday weeks within the global start-end date."""
        weeks = []
        current = self.start_date
        # Advance to next Monday if not already
        while current.weekday() != 0: # 0 = Monday
            current += timedelta(days=1)
        
        while current < self.end_date:
            week_start = current
            week_end = current + timedelta(days=6)
            if week_end > self.end_date:
                break
            weeks.append((week_start, week_end))
            current += timedelta(days=7)
        return weeks

    def _is_on_satellite(self, resident_name: str, week_start: date, week_end: date) -> bool:
        """Checks if a resident is assigned to 'Satellite (L&M)' during this week."""
        # Find which block includes this week
        # Simplification: specific logic to map week -> block
        if self.blocks_df.empty or self.assignments_df.empty:
            return False
            
        for _, block in self.blocks_df.iterrows():
            # If week overlaps with block
            b_start = block['Start Date']
            b_end = block['End Date']
            
            # Check overlap
            if max(b_start, week_start) <= min(b_end, week_end):
                # Check assignment
                block_name = block['Block Name']
                if block_name in self.assignments_df.columns:
                    assignment = self.assignments_df.loc[resident_name, block_name]
                    if assignment == "Satellite (L&M)":
                        return True
        return False

    def _is_on_vacation(self, resident_name: str, start: date, end: date) -> bool:
        """Checks if a resident is on vacation during ANY part of the range."""
        if self.vacations_df.empty:
            return False
            
        resident_vacations = self.vacations_df[self.vacations_df["Resident"] == resident_name]
        for _, row in resident_vacations.iterrows():
            v_start = row["Start Date"]
            v_end = row["End Date"]
            # Check overlap: max(start, v_start) <= min(end, v_end)
            if max(start, v_start) <= min(end, v_end):
                return True
        return False

    def solve_call_schedule(self, pgy_targets: Dict[str, int], locked_schedule: pd.DataFrame = None) -> pd.DataFrame:
        """
        Assigns call weeks to residents.
        pgy_targets: Dict map "PGY-X" -> target weeks.
        locked_schedule: Existing dataframe with "Locked" column.
        """
        self.model = cp_model.CpModel()
        weeks = self._generate_weeks()
        residents = self.residents_df["Name"].tolist()
        attendings = self.attendings_df["Name"].tolist() if not self.attendings_df.empty else []
        
        # Get prior counts
        prior_counts = {}
        for r in residents:
            try:
                row = self.residents_df.loc[self.residents_df["Name"] == r]
                val = row["Call Weeks Completed"].values[0]
                prior_counts[r] = int(val) if pd.notna(val) else 0
            except:
                prior_counts[r] = 0
                
        # Get PGY mapping
        r_pgy = {}
        for r in residents:
            try:
                val = self.residents_df.loc[self.residents_df["Name"] == r, "PGY"].values[0]
                r_pgy[r] = str(val).strip()
            except:
                r_pgy[r] = "PGY-2" # Default
                
        # Parse Locks
        locks = {} # (resident, week_idx) -> bool (True=Must Assigned, False=Must NOT Assigned)
        # Actually simplest is: if locked row says Resident A is on Week 0, force x[A,0]=1.
        # But we also need to force others to 0? Yes, constraint sum=1 handles that.
        # What if the Locked DF has different dates? We match by Week Start.
        if locked_schedule is not None and not locked_schedule.empty and "Locked" in locked_schedule.columns:
            # Filter for locked rows
            locked_rows = locked_schedule[locked_schedule["Locked"] == True]
            for _, row in locked_rows.iterrows():
                # Find matching week index
                w_start = pd.to_datetime(row["Week Start"]).date()
                r_name = row["Resident"]
                
                # Find Index
                for w_idx, (ws, we) in enumerate(weeks):
                    if ws == w_start:
                        if r_name in residents:
                             locks[(r_name, w_idx)] = True
                        break

        # Resident Variables: x[resident, week_index]
        x = {}
        for r in residents:
            for w_idx, _ in enumerate(weeks):
                x[r, w_idx] = self.model.NewBoolVar(f'call_res_{r}_{w_idx}')
                
                # Apply Locks
                if (r, w_idx) in locks:
                    self.model.Add(x[r, w_idx] == 1)

        # Attending Variables: y[attending, week_index]
        y = {}
        if attendings:
            for a in attendings:
                for w_idx, _ in enumerate(weeks):
                    y[a, w_idx] = self.model.NewBoolVar(f'call_att_{a}_{w_idx}')

        # Constraint 1: Exactly one resident per week
        for w_idx, _ in enumerate(weeks):
            self.model.Add(sum(x[r, w_idx] for r in residents) == 1)
            if attendings:
                self.model.Add(sum(y[a, w_idx] for a in attendings) == 1)

        # Constraint 2: Availability (Satellite (L&M) & Vacation) for Residents
        # Skip if Locked!
        for r in residents:
            for w_idx, (w_start, w_end) in enumerate(weeks):
                # If locked, skip checking availability (Manual Override)
                if (r, w_idx) in locks:
                    continue
                    
                # Satellite (L&M)
                if self._is_on_satellite(r, w_start, w_end):
                    self.model.Add(x[r, w_idx] == 0)
                # Vacation
                if self._is_on_vacation(r, w_start, w_end):
                    self.model.Add(x[r, w_idx] == 0)

        # Constraint 3: Meet Total Target (Prior + New) for Residents based on PGY
        deviations = []
        for r in residents:
            pgy = r_pgy.get(r, "PGY-2")
            target = pgy_targets.get(pgy, 18) # Default fallback
            
            needed = max(0, target - prior_counts[r])
            assigned_weeks = sum(x[r, w_idx] for w_idx, _ in enumerate(weeks))
            
            dev = self.model.NewIntVar(0, len(weeks), f'dev_{r}')
            self.model.Add(dev >= needed - assigned_weeks)
            self.model.Add(dev >= assigned_weeks - needed)
            deviations.append(dev)

        # Constraint 4: Balance Attendings (if any)
        att_deviations = []
        if attendings:
            target_att = len(weeks) // len(attendings)
            for a in attendings:
                assigned_weeks_att = sum(y[a, w_idx] for w_idx, _ in enumerate(weeks))
                # Minimize max assignments
                att_deviations.append(assigned_weeks_att) 

        # Objective
        self.model.Minimize(sum(deviations)) # Prioritize PGY targets

        # Solve
        status = self.solver.Solve(self.model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            result = []
            for w_idx, (w_start, w_end) in enumerate(weeks):
                assigned_resident = "Unassigned"
                for r in residents:
                    if self.solver.Value(x[r, w_idx]) == 1:
                        assigned_resident = r
                        break
                
                assigned_attending = "Unassigned"
                if attendings:
                    for a in attendings:
                        if self.solver.Value(y[a, w_idx]) == 1:
                            assigned_attending = a
                            break

                result.append({
                    "Week Start": w_start,
                    "Week End": w_end,
                    "Resident": assigned_resident,
                    "Attending": assigned_attending
                })
            return pd.DataFrame(result)
        else:
            return pd.DataFrame()
        
    def solve_block_schedule(self) -> pd.DataFrame:
        """
        Assigns residents to Attendings, Satellite (L&M), or Elective for each block.
        Constraints:
        1. Each resident has exactly 1 assignment per block.
        2. Satellite (L&M) must have at least 1 resident.
        3. Attendings can take max 1 resident (can be adjusted).
        4. Residents should rotate (unique pairings).
        """
        self.model = cp_model.CpModel()
        
        residents = self.residents_df["Name"].tolist()
        attendings = self.attendings_df["Name"].tolist()
        blocks = self.blocks_df["Block Name"].tolist()
        
        if not residents or not blocks:
            return pd.DataFrame()
        
        # Assignments: Attendings + Special
        assignments = attendings + ["Satellite (L&M)", "Elective"]
        
        # Variables: x[r, b, a]
        x = {}
        for r in residents:
            for b in blocks:
                for a in assignments:
                    x[r, b, a] = self.model.NewBoolVar(f'block_{r}_{b}_{a}')
                    
        # Apply Locks
        if not self.assignments_df.empty:
            for r in residents:
                if r in self.assignments_df.index:
                    for b in blocks:
                        if b in self.assignments_df.columns:
                            assigned_val = self.assignments_df.loc[r, b]
                            if pd.notna(assigned_val) and assigned_val != "Unassigned" and assigned_val in assignments:
                                self.model.Add(x[r, b, assigned_val] == 1)
                                
        # 1. Exact assignment
        for r in residents:
            for b in blocks:
                self.model.Add(sum(x[r, b, a] for a in assignments) == 1)
                
        # 2. Satellite (L&M) Coverage
        for b in blocks:
            self.model.Add(sum(x[r, b, "Satellite (L&M)"] for r in residents) >= 1)
            
        # 3. Attending Capacity (Max 1 per attending)
        for b in blocks:
            for a in attendings:
                self.model.Add(sum(x[r, b, a] for r in residents) <= 1)
                
        # 4. Rotation Logic (Try to maximize unique attendings for each resident)
        # Soft constraint: Penalty for repeating an attending
        repeats = []
        for r in residents:
            for a in attendings:
                # Count how many times resident r is with attending a
                count = sum(x[r, b, a] for b in blocks)
                # We want count <= 1 ideally.
                # Let's minimize count * count or just count if > 1
                # Simple approach: Create a bool for "is with attending a"
                # is_assigned = self.model.NewBoolVar(f'assigned_{r}_{a}')
                # self.model.Add(count >= 1).OnlyEnforceIf(is_assigned) 
                
                # Better: Maximize "assigned at least once".
                # But strict constraint: Try not to repeat.
                # If # blocks < # attendings, we can enforce count <= 1.
                if len(blocks) <= len(attendings):
                     self.model.Add(count <= 1)
                else:
                    # Soft: minimize max(count)
                    pass 

        # Objective: Prioritize Attending assignments over Elective?
        # User said "There's also elective blocks".
        # We want to fill attendings first?
        # Let's maximize the number of Resident-Attending pairings.
        
        attending_assignments = []
        for r in residents:
            for b in blocks:
                for a in attendings:
                    attending_assignments.append(x[r, b, a])
        
        self.model.Maximize(sum(attending_assignments))
        
        status = self.solver.Solve(self.model)
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            # Construct DataFrame: Index=Residents, Cols=Blocks
            data = {}
            for b in blocks:
                col_data = []
                for r in residents:
                    assigned = "Unassigned"
                    for a in assignments:
                        if self.solver.Value(x[r, b, a]) == 1:
                            assigned = a
                            break
                    col_data.append(assigned)
                data[b] = col_data
            
            df = pd.DataFrame(data, index=residents)
            return df
        else:
            return pd.DataFrame()

    def _get_block_for_date(self, d: date) -> pd.Series:
        """Returns the block row that covers the date d, or None."""
        if self.blocks_df.empty:
            return None
        for _, block in self.blocks_df.iterrows():
            if block['Start Date'] <= d <= block['End Date']:
                return block
        return None

    def _get_assigned_attending(self, resident_name: str, d: date) -> Optional[str]:
        """Returns the assigned attending/rotation name for a resident on a specific date."""
        block = self._get_block_for_date(d)
        if block is not None and not self.assignments_df.empty:
            block_name = block['Block Name']
            if block_name in self.assignments_df.columns:
                 if resident_name in self.assignments_df.index:
                    return self.assignments_df.loc[resident_name, block_name]
        return None

    def solve_inpatient_schedule(self, target_days_per_resident: Optional[int] = None) -> pd.DataFrame:
        """
        Assigns inpatient duties for weekdays (Mon-Fri).
        """
        self.model = cp_model.CpModel()
        
        # Generate weekdays (Mon-Fri)
        days = []
        current = self.start_date
        while current <= self.end_date:
            if current.weekday() < 5: # Mon=0, Fri=4
                days.append(current)
            current += timedelta(days=1)
            
        residents = self.residents_df["Name"].tolist()
        
        # Variables: x[resident, day_index]
        x = {}
        for r in residents:
            for d_idx, _ in enumerate(days):
                x[r, d_idx] = self.model.NewBoolVar(f'inpatient_{r}_{d_idx}')
                
        # Constraint 1: Exactly one resident per day
        for d_idx, _ in enumerate(days):
            self.model.Add(sum(x[r, d_idx] for r in residents) == 1)
            
        # Apply Locks
        locked_inpatient_days = {}
        if not self.inpatient_df.empty and "Locked" in self.inpatient_df.columns:
            locked_rows = self.inpatient_df[self.inpatient_df["Locked"] == True]
            for _, row in locked_rows.iterrows():
                locked_date = pd.to_datetime(row["Date"]).date()
                if row["Resident"] in residents:
                    locked_inpatient_days[locked_date] = row["Resident"]
                    
        # Coverage overlaps (to prevent resident on coverage from doing inpatient)
        locked_coverage_days = set() # (date, resident)
        if not self.coverage_df.empty and "Locked" in self.coverage_df.columns:
             locked_rows = self.coverage_df[self.coverage_df["Locked"] == True]
             for _, row in locked_rows.iterrows():
                 locked_date = pd.to_datetime(row["Date"]).date()
                 cov_res = row.get("Covering Resident")
                 if cov_res in residents:
                     locked_coverage_days.add((locked_date, cov_res))
            
        # Constraint 2: Availability & Conflicts
        for r in residents:
            for d_idx, d in enumerate(days):
                # Lock enforcement
                if d in locked_inpatient_days:
                    if locked_inpatient_days[d] == r:
                        self.model.Add(x[r, d_idx] == 1)
                    else:
                        self.model.Add(x[r, d_idx] == 0)
                    continue
                    
                # Coverage overlap
                if (d, r) in locked_coverage_days:
                    self.model.Add(x[r, d_idx] == 0)
                    continue
                    
                # 2a. Satellite (L&M) Rule
                if self._is_on_satellite(r, d, d):
                    self.model.Add(x[r, d_idx] == 0)
                    continue

                # 2b. Vacation Rule
                if self._is_on_vacation(r, d, d):
                    self.model.Add(x[r, d_idx] == 0)
                    continue
                
                # 2c. Attending Clinic Days Conflict
                assignment = self._get_assigned_attending(r, d)
                if assignment and assignment in self.attendings_df["Name"].values:
                    # Lookup attending clinic days
                    attending_row = self.attendings_df[self.attendings_df["Name"] == assignment].iloc[0]
                    clinic_days_str = str(attending_row["Clinic Days"])
                    day_name = d.strftime("%A")
                    
                    # If the day name is in the clinic days string (e.g. "Monday, Tuesday")
                    if day_name in clinic_days_str:
                         self.model.Add(x[r, d_idx] == 0)

        # Objective: Balance or Target
        # If target provided, try to meet it. Otherwise, minimize deviation.
        # For simplicity, let's enforce a soft upper bound to spread load.
        
        total_days = len(days)
        avg_load = total_days // len(residents)
        
        # Add a slack variable for each resident to minimize deviation
        # This is a bit complex for a quick implementation, let's just limit max days 
        # to ensure distribution is somewhat fair if possible.
        max_load = avg_load + 5 
        for r in residents:
             self.model.Add(sum(x[r, d_idx] for d_idx, _ in enumerate(days)) <= max_load)

        # Solve
        status = self.solver.Solve(self.model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            result = []
            for d_idx, d in enumerate(days):
                assigned_resident = "Unassigned"
                for r in residents:
                    if self.solver.Value(x[r, d_idx]) == 1:
                        assigned_resident = r
                        break
                result.append({
                    "Date": d,
                    "Day": d.strftime("%A"),
                    "Resident": assigned_resident
                })
            return pd.DataFrame(result)
        else:
            return pd.DataFrame()

    def solve_cross_coverage(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Identifies days where an attending needs coverage because their assigned resident is on vacation.
        Assigns an available resident to cover.
        Returns: (coverage_schedule_df, stats_df)
        """
        # 1. Identify all needed coverage slots
        # Iterate through all weekdays in the schedule range
        current = self.start_date
        needed_coverage = [] # (Date, Attending, Resident_Away)
        
        while current <= self.end_date:
            if current.weekday() < 5: # Mon-Fri only? Usually coverage is M-F. Weekends are Call.
                # Check each resident
                for r in self.residents_df["Name"].tolist():
                    # Is resident assigned to an Attending?
                    assigned_attending = self._get_assigned_attending(r, current)
                    if assigned_attending and assigned_attending in self.attendings_df["Name"].values:
                        # 1. Check if Attending has Clinic today
                        att_row = self.attendings_df[self.attendings_df["Name"] == assigned_attending].iloc[0]
                        clinic_days = str(att_row["Clinic Days"])
                        day_name = current.strftime("%A")
                        
                        if day_name in clinic_days:
                            # 2. Is resident on vacation?
                            if self._is_on_vacation(r, current, current):
                                needed_coverage.append({
                                    "Date": current,
                                    "Attending Needed": assigned_attending,
                                    "Resident Away": r
                                })
            current += timedelta(days=1)
            
        if not needed_coverage:
            return pd.DataFrame(), pd.DataFrame()
            
        # 2. Assign Coverage
        coverage_log = []
        resident_counts = {r: 0 for r in self.residents_df["Name"].tolist()}
        
        # Sort by date to simulate chronological assignment
        import random
        needed_coverage.sort(key=lambda x: x["Date"])
        
        # Track who is covering on a specific day to avoid double booking
        # (Day, Resident) -> bool
        daily_assignments = {} 
        
        # Parse existing locks
        existing_locks = {} # (Date, Attending) -> Covering Resident
        if not self.coverage_df.empty and "Locked" in self.coverage_df.columns:
            locked_rows = self.coverage_df[self.coverage_df["Locked"] == True]
            for _, row in locked_rows.iterrows():
                ld = pd.to_datetime(row["Date"]).date()
                att = row.get("Attending Needed")
                c_res = row.get("Covering Resident")
                if c_res in self.residents_df["Name"].values:
                    existing_locks[(ld, att)] = c_res
                    
        # Parse inpatient exact schedule
        inpatient_assignments = set() # (Date, Resident)
        if not self.inpatient_df.empty:
            for _, row in self.inpatient_df.iterrows():
                 ld = pd.to_datetime(row["Date"]).date()
                 r = row.get("Resident")
                 inpatient_assignments.add((ld, r))

        for slot in needed_coverage:
            d = slot["Date"]
            attending = slot["Attending Needed"]
            away_resident = slot["Resident Away"]
            
            # Check lock
            if (d, attending) in existing_locks:
                selected = existing_locks[(d, attending)]
                resident_counts[selected] += 1
                daily_assignments[(d, selected)] = True
                coverage_log.append({
                    "Date": d,
                    "Day": d.strftime("%A"),
                    "Resident Away": away_resident,
                    "Attending Needed": attending,
                    "Covering Resident": selected,
                    "Locked": True
                })
                continue
            
            candidates = []
            for r in self.residents_df["Name"].tolist():
                # Cannot cover if:
                # 1. Is the away resident (obv)
                if r == away_resident: continue
                # 2. Is on vacation themselves
                if self._is_on_vacation(r, d, d): continue
                # 3. Is on Satellite (L&M) (rigid rotation)
                if self._is_on_satellite(r, d, d): continue
                # 4. Is already covering someone today
                if daily_assignments.get((d, r), False): continue
                # 5. Is already on inpatient today?
                if (d, r) in inpatient_assignments: continue
                
                # 5. Is Assigned to what?
                # If assigned to Elective/Research, they are FREE to cover.
                # If assigned to another Attending, can they cover?
                # "Resident covers a service...". Usually means pulling someone from Elective/Research/Distant rotation 
                # OR someone on a light service.
                # User did not specify strict availability rules.
                # Let's assume ANYONE not on Vacation/Satellite/Locked is fair game, 
                # BUT we prefer those on Elective/Research if possible? 
                # User asked for "fairly distributed", implying spread load among everyone.
                # Let's count everyone eligible except Sat/Vac/Self.
                
                candidates.append(r)
                
            if candidates:
                # Sort candidates by current coverage count (asc), then random
                random.shuffle(candidates)
                candidates.sort(key=lambda x: resident_counts[x])
                
                selected = candidates[0]
                resident_counts[selected] += 1
                daily_assignments[(d, selected)] = True
                
                coverage_log.append({
                    "Date": d,
                    "Day": d.strftime("%A"),
                    "Resident Away": away_resident,
                    "Attending Needed": attending,
                    "Covering Resident": selected
                })
            else:
                coverage_log.append({
                    "Date": d,
                    "Day": d.strftime("%A"),
                    "Resident Away": away_resident,
                    "Attending Needed": attending,
                    "Covering Resident": "UNFILLED - No Candidates"
                })
                
        # 3. Create DataFrames
        coverage_df = pd.DataFrame(coverage_log)
        
        stats = pd.DataFrame(list(resident_counts.items()), columns=["Resident", "Days Covered"])
        stats = stats.sort_values("Days Covered", ascending=False)
        
        return coverage_df, stats
