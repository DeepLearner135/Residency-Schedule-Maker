import streamlit as st
import pandas as pd
from datetime import date, timedelta
from models import Resident, Attending
import utils

st.set_page_config(page_title="Residency Schedule Maker", layout="wide")

st.title("Radiation Oncology Residency Schedule Maker")

# Initialize Session State
if 'residents_df' not in st.session_state:
    st.session_state.residents_df = pd.DataFrame(columns=["Name", "PGY", "Call Weeks Completed", "Inpatient Days Completed", "Prior Electives"])

if 'attendings_df' not in st.session_state:
    st.session_state.attendings_df = pd.DataFrame(columns=["Name", "Clinic Days"])

if 'vacations_df' not in st.session_state:
        st.session_state.vacations_df = pd.DataFrame(columns=["Resident", "Start Date", "End Date"])

if 'blocks_df' not in st.session_state:
    st.session_state.blocks_df = pd.DataFrame(columns=["Block Name", "Start Date", "End Date"])

if 'lectures_df' not in st.session_state:
    st.session_state.lectures_df = pd.DataFrame(columns=["Date", "Unit", "Time Slot", "Topic/Speaker"])

# Sidebar
with st.sidebar:
    st.header("Settings")
    # Default: 7/6/26 to 6/25/27
    default_start = date(2026, 7, 6)
    default_end = date(2027, 6, 25)
    
    start_date = st.date_input("Schedule Start Date", value=default_start, format="MM/DD/YYYY")
    end_date = st.date_input("Schedule End Date", value=default_end, format="MM/DD/YYYY")
    
    st.divider()
    st.header("Data Import")
    uploaded_file = st.file_uploader("Upload Personnel CSV (Residents & Attendings)", type="csv")
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
            # Normalize columns
            required_cols = ["Name", "Role"]
            if not all(col in df.columns for col in required_cols):
                 st.error(f"CSV must contain {required_cols}")
            else:
                # Split into Residents and Attendings
                residents_mask = df["Role"].str.lower().str.contains("resident")
                attendings_mask = df["Role"].str.lower().str.contains("attending")
                
                # Process Residents
                res_df = df[residents_mask].copy()
                # Ensure columns exist
                # Calls/Inpatient are "Prior" counts
                desired_cols = ["PGY", "Call Weeks Completed", "Inpatient Days Completed", "Prior Electives"]
                for col in desired_cols:
                    if col not in res_df.columns:
                        res_df[col] = 0 if "Completed" in col or "Prior" in col else ""
                
                st.session_state.residents_df = res_df[["Name"] + desired_cols]
                
                # Process Attendings
                att_df = df[attendings_mask].copy()
                if "Clinic Days" not in att_df.columns:
                    att_df["Clinic Days"] = ""
                st.session_state.attendings_df = att_df[["Name", "Clinic Days"]]
                
                st.success(f"Loaded {len(res_df)} residents and {len(att_df)} attendings.")
                
        except Exception as e:
            st.error(f"Error processing file: {e}")

# Tabs
tab_home, tab_residents, tab_blocks, tab_call, tab_inpatient, tab_vacation, tab_coverage, tab_lectures, tab_export = st.tabs([
    "Home", "Residents & Attendings", "Block Schedule", "Call Schedule", "Inpatient Schedule", "Vacation", "Cross Coverage", "Lecture Schedule", "Export"
])

with tab_home:
    st.title("About")
    try:
        with open("README.md", "r") as f:
            readme_content = f.read()
            st.markdown(readme_content)
    except FileNotFoundError:
        st.error("README.md not found.")
    
    st.divider()
    st.markdown("🔗 **[View Project on GitHub](https://github.com/DeepLearner135/Residency-Schedule-Maker)**")

with tab_residents:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Residents")
        st.info("Edit resident details below. 'Call Weeks Completed' and 'Inpatient Days Completed' are prior totals.")
        st.session_state.residents_df = st.data_editor(
            st.session_state.residents_df, 
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "PGY": st.column_config.SelectboxColumn(
                    "PGY",
                    options=["PGY-2", "PGY-3", "PGY-4", "PGY-5"],
                    required=True
                )
            },
            key="residents_editor"
        )
        
    with col2:
        st.subheader("Attendings")
        st.info("Edit attending details. 'Clinic Days' should be comma-separated (e.g., 'Monday, Tuesday').")
        st.session_state.attendings_df = st.data_editor(st.session_state.attendings_df, num_rows="dynamic", use_container_width=True, key="attendings_editor")

with tab_blocks:
    st.header("Block Schedule")
    
    # 1. Define Blocks
    st.subheader("1. Define Blocks")
    
    col_b1, col_b2 = st.columns([1, 2])
    with col_b1:
        # Auto-Generation
        if st.button("Auto-Generate Blocks (2-Months)"):
            blocks = []
            curr = start_date
            i = 1
            while curr < end_date:
                # 2 Month chunks roughly
                # Simple logic: Add 60 days or use month arithmetic
                # Let's use exact months if possible, or just 8 weeks? User said "2-month blocks".
                # Let's try to advance month by 2.
                next_month = curr.month + 2
                next_year = curr.year
                if next_month > 12:
                    next_month -= 12
                    next_year += 1
                
                # Careful with days (e.g. Jan 31 -> Mar 31? Mar 30?)
                # Let's just go to the 1st of the next-next month and subtract a day?
                # Usually blocks align with months.
                # Assuming start_date is start of a month.
                
                # Simplified: 8 weeks (56 days) or just use dateutil.
                # Let's use a simpler heuristic: block end is (curr + 2 months) - 1 day.
                import calendar
                t_month = curr.month + 2
                t_year = curr.year + (t_month - 1) // 12
                t_month = (t_month - 1) % 12 + 1
                
                # Day...
                # If start is 1st, end is last of prev month.
                # Let's pick strict dates: Start + ~60 days.
                res_end = date(t_year, t_month, 1) - timedelta(days=1)
                
                if res_end > end_date:
                    res_end = end_date
                
                blocks.append({
                    "Block Name": f"Block {i}",
                    "Start Date": curr,
                    "End Date": res_end
                })
                
                curr = res_end + timedelta(days=1)
                i += 1
                
            st.session_state.blocks_df = pd.DataFrame(blocks)
            st.success(f"Generated {len(blocks)} blocks.")

    # UI to add a new block
    with st.expander("Manually Add New Block"):
        with st.form("add_block_form"):
            b_name = st.text_input("Block Name (e.g., Block 1)")
            b_start = st.date_input("Start Date", format="MM/DD/YYYY")
            b_end = st.date_input("End Date", format="MM/DD/YYYY")
            submitted = st.form_submit_button("Add Block")
            if submitted and b_name:
                new_block = pd.DataFrame({"Block Name": [b_name], "Start Date": [b_start], "End Date": [b_end]})
                st.session_state.blocks_df = pd.concat([st.session_state.blocks_df, new_block], ignore_index=True)
                st.success(f"Added {b_name}")

    st.session_state.blocks_df = st.data_editor(
        st.session_state.blocks_df,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "Start Date": st.column_config.DateColumn("Start Date", format="MM/DD/YYYY"),
            "End Date": st.column_config.DateColumn("End Date", format="MM/DD/YYYY")
        },
        key="blocks_editor"
    )

    # 2. Assign Residents to Blocks
    st.divider()
    st.subheader("2. Assign Residents to Blocks")
    
    # Auto-Assignment Button
    lock_blocks = st.checkbox("Lock current assignments", value=True, help="If checked, currently assigned rotations won't be changed.")
    if st.button("Auto-Assign Rotations (Solver)"):
        from solver import ScheduleSolver
        if not st.session_state.blocks_df.empty and not st.session_state.residents_df.empty:
             current_assignments = st.session_state.block_assignments if lock_blocks and 'block_assignments' in st.session_state else pd.DataFrame()
             solver = ScheduleSolver(
                st.session_state.residents_df,
                st.session_state.attendings_df,
                st.session_state.blocks_df,
                current_assignments,
                st.session_state.vacations_df,
                start_date,
                end_date,
                st.session_state.get('inpatient_schedule_df'),
                st.session_state.get('coverage_df')
            )
             with st.spinner("Assigning Rotations..."):
                 assignments = solver.solve_block_schedule()
                 
             if not assignments.empty:
                 st.session_state.block_assignments = assignments
                 st.success("Rotations Assigned!")
             else:
                 st.error("Could not find feasible rotation schedule.")
        else:
            st.error("Missing Residents or Blocks.")

    if not st.session_state.blocks_df.empty and not st.session_state.residents_df.empty:
        # Create a matrix: Rows=Residents, Cols=Blocks
        block_names = st.session_state.blocks_df["Block Name"].tolist()
        resident_names = st.session_state.residents_df["Name"].tolist()
        
        # Initialize assignments if not exists
        if 'block_assignments' not in st.session_state:
            st.session_state.block_assignments = pd.DataFrame(index=resident_names, columns=block_names)
        
        # Sync index/columns if residents/blocks changed
        st.session_state.block_assignments = st.session_state.block_assignments.reindex(index=resident_names, columns=block_names)

        # Options for dropdown (Attendings + Special Rotations)
        attending_options = st.session_state.attendings_df["Name"].tolist() if not st.session_state.attendings_df.empty else []
        options = ["Satellite (L&M)", "Satellite (Proton)", "Elective", "Research"] + attending_options
        
        column_config = {}
        for col in block_names:
            # Lookup dates
            block_row = st.session_state.blocks_df[st.session_state.blocks_df["Block Name"] == col]
            if not block_row.empty:
                s_date = pd.to_datetime(block_row.iloc[0]["Start Date"]).strftime("%m/%d")
                e_date = pd.to_datetime(block_row.iloc[0]["End Date"]).strftime("%m/%d")
                label = f"{col} ({s_date}-{e_date})"
            else:
                label = col
                
            column_config[col] = st.column_config.SelectboxColumn(
                label=label,
                options=options,
                required=False
            )
        
        st.write("Assign an Attending or Rotation (e.g. Satellite (L&M) or Satellite (Proton)) for each resident per block.")
        st.info("💡 **Tip:** To create combined rotations (e.g., 'Dr. A & Dr. B') or split blocks, simply add them as a new 'Attending' in the **Residents & Attendings** tab.")
        
        edited_assignments = st.data_editor(
            st.session_state.block_assignments.reset_index(), # Reset index to show resident names as a column
            column_config=column_config,
            disabled=["index"], # Disable editing the resident name
            hide_index=True,
            use_container_width=True,
            key="block_assignments_editor"
        )
        
        # Save back to session state (setting index back to resident name)
        if edited_assignments is not None:
             st.session_state.block_assignments = edited_assignments.set_index("index")
             st.session_state.block_assignments.index.name = None # Clean up index name

        # Statistics & Tally
        st.divider()
        col_s1, col_s2 = st.columns(2)
        
        with col_s1:
            st.subheader("Rotation Statistics")
            if not st.session_state.block_assignments.empty:
                # Calculate counts per resident
                stats_data = []
                for r in resident_names:
                    # Get Prior
                    prior_el = 0
                    prior_sat = 0 
                    # Lookup prior
                    try:
                        row = st.session_state.residents_df[st.session_state.residents_df["Name"] == r].iloc[0]
                        if "Prior Electives" in row:
                            prior_el = int(row["Prior Electives"]) if pd.notna(row["Prior Electives"]) else 0
                    except:
                        pass
                    
                    # Get Scheduled
                    row_assign = st.session_state.block_assignments.loc[r]
                    sched_el = row_assign.astype(str).str.contains("Elective", case=False).sum()
                    sched_sat_lm = row_assign.astype(str).str.contains("Satellite (L&M)", case=False, regex=False).sum()
                    sched_sat_pr = row_assign.astype(str).str.contains("Satellite (Proton)", case=False, regex=False).sum()
                    
                    stats_data.append({
                        "Resident": r,
                        "Total Electives": prior_el + sched_el,
                        "Satellite (L&M)": sched_sat_lm,
                        "Satellite (Proton)": sched_sat_pr,
                        "Prior Electives": prior_el,
                        "Scheduled Electives": sched_el
                    })
                
                st.dataframe(pd.DataFrame(stats_data), use_container_width=True)
                
        with col_s2:
            st.subheader("Attending Coverage Tally")
            if not st.session_state.block_assignments.empty and not st.session_state.attendings_df.empty:
                tally_data = {}
                # For each Block
                for b in block_names:
                    col_tally = []
                    # Get all assignments in this block
                    if b in st.session_state.block_assignments.columns:
                        block_entries = st.session_state.block_assignments[b].dropna().astype(str).tolist()
                        combined_string = " ".join(block_entries)
                        
                        # Check each attending / satellite
                        tally_entities = attending_options + ["Satellite (L&M)", "Satellite (Proton)"]
                        for a in tally_entities:
                            # if attending/satellite name is in combined_string (handles "Dr. A / Dr. B")
                            if a in combined_string:
                                col_tally.append("✅")
                            else:
                                col_tally.append("❌")
                    else:
                        tally_entities = attending_options + ["Satellite (L&M)", "Satellite (Proton)"]
                        col_tally = ["❌"] * len(tally_entities)
                    tally_data[b] = col_tally
                    
                tally_df = pd.DataFrame(tally_data, index=tally_entities)
                st.dataframe(tally_df, use_container_width=True)

    else:
        st.warning("Please add Residents and Blocks first.")

with tab_call:
    st.header("Call Schedule")
    
    col_c1, col_c2 = st.columns([1, 3])
    
    with col_c1:
        st.subheader("Configuration")
        
        # PGY Targets
        st.markdown("**Target Weeks per PGY**")
        col_pgy2, col_pgy3, col_pgy4 = st.columns(3)
        pgy_targets = {}
        with col_pgy2:
            pgy_targets["PGY-2"] = st.number_input("PGY-2", min_value=0, value=6)
        with col_pgy3:
            pgy_targets["PGY-3"] = st.number_input("PGY-3", min_value=0, value=12)
        with col_pgy4:
            pgy_targets["PGY-4"] = st.number_input("PGY-4", min_value=0, value=15)
        # PGY-5 usually 0, but implicit
        
        if st.button("Generate Call Schedule"):
            from solver import ScheduleSolver # Import here to avoid circularity if any
            
            # Prepare data
            if 'blocks_df' in st.session_state and 'residents_df' in st.session_state and 'block_assignments' in st.session_state:
                # Check for Locked Assignments
                locked_assignments = []
                if 'call_schedule_df' in st.session_state and not st.session_state.call_schedule_df.empty:
                    # If "Locked" column exists and is checked? Or just assume existing are locked?
                    # User said "Make a manual edit... take priority".
                    # Let's assume if the table exists, we respect it as "Prior Assignments" or we add a "Locked" col.
                    # Simpler: Just pass the current df as 'locked_df' to solver?
                    # Let's add a "Lock" checkbox to the dataframe
                    pass 

                solver = ScheduleSolver(
                    st.session_state.residents_df,
                    st.session_state.attendings_df,
                    st.session_state.blocks_df,
                    st.session_state.block_assignments,
                    st.session_state.vacations_df,
                    start_date,
                    end_date,
                    st.session_state.get('inpatient_schedule_df'),
                    st.session_state.get('coverage_df')
                )
                
                with st.spinner("Solving..."):
                    # Pass targets dictionary. We'll update solver signature next.
                    # We also pass the current schedule to respect locks (to be implemented)
                    curr_sched = st.session_state.call_schedule_df if 'call_schedule_df' in st.session_state else pd.DataFrame()
                    result_df = solver.solve_call_schedule(pgy_targets=pgy_targets, locked_schedule=curr_sched)
                
                if not result_df.empty:
                    st.session_state.call_schedule_df = result_df
                    st.success("Schedule Generated!")
                else:
                    st.error("Could not find a feasible schedule. Check constraints.")
            else:
                st.error("Please define Residents and Blocks first.")

    with col_c2:
        st.subheader("Schedule")
        if 'call_schedule_df' in st.session_state:
            # Ensure 'Locked' column exists
            if "Locked" not in st.session_state.call_schedule_df.columns:
                st.session_state.call_schedule_df["Locked"] = False
                
            # Get lists for dropdowns
            resident_names = st.session_state.residents_df["Name"].tolist() if "residents_df" in st.session_state else []
            attending_names = st.session_state.attendings_df["Name"].tolist() if "attendings_df" in st.session_state else []
            
            st.session_state.call_schedule_df = st.data_editor(
                st.session_state.call_schedule_df,
                column_config={
                    "Locked": st.column_config.CheckboxColumn(
                        "Lock",
                        help="Lock this assignment to prevent changes during re-solving",
                        default=False,
                    ),
                    "Resident": st.column_config.SelectboxColumn(
                        "Resident",
                        options=resident_names,
                        required=True
                    ),
                    "Attending": st.column_config.SelectboxColumn(
                        "Attending",
                        options=attending_names + ["Unassigned"],
                        required=False
                    )
                },
                num_rows="fixed",
                hide_index=True,
                use_container_width=True,
                key="call_schedule_editor"
            )
            
            # Stats
            st.write("### Stats")
            counts = st.session_state.call_schedule_df["Resident"].value_counts().reset_index()
            counts.columns = ["Resident", "Assigned Weeks"]
            st.dataframe(counts)

with tab_inpatient:
    st.header("Inpatient Schedule")
    
    col_i1, col_i2 = st.columns([1, 3])
    
    with col_i1:
        lock_inpatient = st.checkbox("Lock current inpatient assignments", value=True, help="If checked, locked days won't be changed.")
        if st.button("Generate Inpatient Schedule"):
            from solver import ScheduleSolver
            
            if 'blocks_df' in st.session_state and 'residents_df' in st.session_state and 'block_assignments' in st.session_state:
                solver = ScheduleSolver(
                    st.session_state.residents_df,
                    st.session_state.attendings_df,
                    st.session_state.blocks_df,
                    st.session_state.block_assignments,
                    st.session_state.vacations_df,
                    start_date,
                    end_date,
                    st.session_state.get('inpatient_schedule_df') if lock_inpatient else None,
                    st.session_state.get('coverage_df')
                )
                
                with st.spinner("Solving Inpatient Schedule..."):
                    result_df = solver.solve_inpatient_schedule()
                
                if not result_df.empty:
                    st.session_state.inpatient_schedule_df = result_df
                    st.success("Inpatient Schedule Generated!")
                else:
                    st.error("No feasible inpatient schedule found.")
            else:
                 st.error("Please define Residents and Blocks first.")

    with col_i2:
        if 'inpatient_schedule_df' in st.session_state:
            if "Locked" not in st.session_state.inpatient_schedule_df.columns:
                st.session_state.inpatient_schedule_df.insert(0, "Locked", False)
                
            resident_names = st.session_state.residents_df["Name"].tolist() if "residents_df" in st.session_state else []
            
            st.session_state.inpatient_schedule_df = st.data_editor(
                st.session_state.inpatient_schedule_df,
                column_config={
                    "Locked": st.column_config.CheckboxColumn(
                        "Lock",
                        help="Lock this assignment",
                        default=False,
                    ),
                    "Resident": st.column_config.SelectboxColumn(
                        "Resident",
                        options=resident_names,
                        required=True
                    )
                },
                num_rows="fixed",
                hide_index=True,
                use_container_width=True,
                key="inpatient_schedule_editor"
            )
            
            # Stats
            st.write("### Stats")
            i_counts = st.session_state.inpatient_schedule_df["Resident"].value_counts().reset_index()
            i_counts.columns = ["Resident", "Assigned Days"]
            st.dataframe(i_counts)

with tab_vacation:
    st.header("Vacation Requests")
    
 
            
    # Re-implmenting Vacation Form with auto-update
    # We'll use columns to make it look like a form row
    st.write("**Add Vacation Request**")
    col_v1, col_v2, col_v3, col_v4 = st.columns([2, 1, 1, 1])
    
    with col_v1:
        v_resident = st.selectbox("Resident", options=st.session_state.residents_df["Name"].tolist() if not st.session_state.residents_df.empty else [], key="vac_res")
        
    with col_v2:
        # Callback to update end date
        def on_vac_start_change():
            if 'vac_start' in st.session_state:
                st.session_state.vac_end = st.session_state.vac_start + timedelta(days=4)
        
        v_start = st.date_input("Start", key="vac_start", format="MM/DD/YYYY", on_change=on_vac_start_change)
        
    with col_v3:
         v_end = st.date_input("End", key="vac_end", format="MM/DD/YYYY")
         
    with col_v4:
        # Align button
        st.write("")
        st.write("")
        if st.button("Add"):
            if v_resident and v_start <= v_end:
                new_vac = pd.DataFrame({"Resident": [v_resident], "Start Date": [v_start], "End Date": [v_end]})
                st.session_state.vacations_df = pd.concat([st.session_state.vacations_df, new_vac], ignore_index=True)
                st.success(f"Added {v_resident}")
            else:
                st.error("Invalid")

    st.subheader("Current Vacation Requests")
    st.session_state.vacations_df = st.data_editor(
        st.session_state.vacations_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Start Date": st.column_config.DateColumn("Start Date", format="MM/DD/YYYY"),
            "End Date": st.column_config.DateColumn("End Date", format="MM/DD/YYYY")
        },
        key="vacations_editor"
    )

with tab_coverage:
    st.header("Cross Coverage")
    st.write("Automatically identify and assign coverage for when residents are on vacation.")
    
    col_cov1, col_cov2 = st.columns([2, 1])
    
    with col_cov1:
        lock_coverage = st.checkbox("Lock current cross coverage assignments", value=True, help="If checked, locked days won't be changed.")
        if st.button("Generate Cross Coverage"):
            from solver import ScheduleSolver
            
            if 'blocks_df' in st.session_state and 'residents_df' in st.session_state and 'block_assignments' in st.session_state:
                solver = ScheduleSolver(
                    st.session_state.residents_df,
                    st.session_state.attendings_df,
                    st.session_state.blocks_df,
                    st.session_state.block_assignments,
                    st.session_state.vacations_df,
                    start_date,
                    end_date,
                    st.session_state.get('inpatient_schedule_df'),
                    st.session_state.get('coverage_df') if lock_coverage else None
                )
                
                with st.spinner("Calculating Coverage Needs..."):
                    cov_df, cov_stats = solver.solve_cross_coverage()
                
                if not cov_df.empty:
                    st.session_state.coverage_df = cov_df
                    st.session_state.coverage_stats = cov_stats
                    st.success("Cross Coverage Generated!")
                else:
                    st.info("No coverage needed (no residents on vacation during assigned blocks).")
                    st.session_state.coverage_df = pd.DataFrame()
                    st.session_state.coverage_stats = pd.DataFrame()
            else:
                st.error("Please define Residents, Blocks, and Assignments first.")

        if 'coverage_df' in st.session_state and not st.session_state.coverage_df.empty:
            st.subheader("Coverage Schedule")
            if "Locked" not in st.session_state.coverage_df.columns:
                st.session_state.coverage_df.insert(0, "Locked", False)
                
            resident_names = st.session_state.residents_df["Name"].tolist() if "residents_df" in st.session_state else []
            
            # Enable row deletion and editing
            st.session_state.coverage_df = st.data_editor(
                st.session_state.coverage_df,
                column_config={
                    "Locked": st.column_config.CheckboxColumn(
                        "Lock",
                        help="Lock this assignment",
                        default=False,
                    ),
                    "Covering Resident": st.column_config.SelectboxColumn(
                        "Covering Resident",
                        options=resident_names,
                        required=True
                    )
                },
                num_rows="dynamic",
                hide_index=True,
                use_container_width=True,
                key="coverage_editor"
            )
            
    with col_cov2:
        if 'coverage_stats' in st.session_state and not st.session_state.coverage_stats.empty:
            st.subheader("Coverage Stats")
            st.dataframe(st.session_state.coverage_stats, use_container_width=True)

with tab_lectures:
    st.header("Lecture Schedule")
    st.write("Manage daily lectures and educational events.")
    
    # 1. Quick Add Form
    with st.expander("Add New Lecture"):
        with st.form("add_lecture_form"):
            col_l1, col_l2, col_l3, col_l4 = st.columns(4)
            with col_l1:
                l_date = st.date_input("Date", format="MM/DD/YYYY")
            with col_l2:
                l_unit = st.text_input("Unit (e.g. CNS)")
            with col_l3:
                time_slots = ["7:30-8:30 AM", "8-9 AM", "9-10 AM", "12-1 PM", "Other"]
                l_slot = st.selectbox("Time Slot", options=time_slots)
            with col_l4:
                l_topic = st.text_input("Topic / Speaker")
                
            submitted = st.form_submit_button("Add Lecture")
            if submitted and l_topic and l_unit:
                new_lec = pd.DataFrame({
                    "Date": [l_date],
                    "Unit": [l_unit],
                    "Time Slot": [l_slot],
                    "Topic/Speaker": [l_topic]
                })
                st.session_state.lectures_df = pd.concat([st.session_state.lectures_df, new_lec], ignore_index=True)
                st.success("Lecture Added!")

    st.subheader("Current Lectures")
    if not st.session_state.lectures_df.empty:
        t_options = ["7:30-8:30 AM", "8-9 AM", "9-10 AM", "12-1 PM", "Other"]
        
        st.session_state.lectures_df = st.data_editor(
            st.session_state.lectures_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Date": st.column_config.DateColumn("Date", format="MM/DD/YYYY"),
                "Unit": st.column_config.TextColumn("Unit"),
                "Time Slot": st.column_config.SelectboxColumn("Time Slot", options=t_options),
                "Topic/Speaker": st.column_config.TextColumn("Topic/Speaker")
            },
            key="lectures_editor"
        )
    else:
        st.info("No lectures added yet.")

with tab_export:
    st.header("Export & Import")
    
    col_ex1, col_ex2 = st.columns(2)
    
    with col_ex1:
        st.subheader("Export State")
        if st.button("Download Schedule & State (Excel)"):
            import io
            from datetime import datetime
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                # 1. Main Schedules
                if 'call_schedule_df' in st.session_state:
                    st.session_state.call_schedule_df.to_excel(writer, sheet_name='Call Schedule', index=False)
                if 'inpatient_schedule_df' in st.session_state:
                    st.session_state.inpatient_schedule_df.to_excel(writer, sheet_name='Inpatient Schedule', index=False)
                if 'block_assignments' in st.session_state:
                    # Rename columns to include dates if possible
                    export_assignments = st.session_state.block_assignments.copy()
                    if 'blocks_df' in st.session_state and not st.session_state.blocks_df.empty:
                        new_cols = []
                        for col in export_assignments.columns:
                            b_row = st.session_state.blocks_df[st.session_state.blocks_df["Block Name"] == col]
                            if not b_row.empty:
                                s_date = pd.to_datetime(b_row.iloc[0]["Start Date"]).strftime("%m/%d/%Y")
                                e_date = pd.to_datetime(b_row.iloc[0]["End Date"]).strftime("%m/%d/%Y")
                                new_cols.append(f"{col} ({s_date} - {e_date})")
                            else:
                                new_cols.append(col)
                        export_assignments.columns = new_cols
                    export_assignments.to_excel(writer, sheet_name='Block Assignments')
                
                # 2. Configuration Data (For Restore)
                if 'residents_df' in st.session_state:
                    st.session_state.residents_df.to_excel(writer, sheet_name='Residents', index=False)
                if 'attendings_df' in st.session_state:
                    st.session_state.attendings_df.to_excel(writer, sheet_name='Attendings', index=False)
                if 'blocks_df' in st.session_state:
                    st.session_state.blocks_df.to_excel(writer, sheet_name='Blocks', index=False)
                if 'vacations_df' in st.session_state:
                    st.session_state.vacations_df.to_excel(writer, sheet_name='Vacations', index=False)
                if 'lectures_df' in st.session_state:
                    st.session_state.lectures_df.to_excel(writer, sheet_name='Lectures', index=False)
                    
                # 3. Metadata
                metadata = pd.DataFrame({
                    "Key": ["Last Updated", "Software Version"],
                    "Value": [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "1.1"]
                })
                metadata.to_excel(writer, sheet_name='Metadata', index=False)
                
                # 4. Inpatient Calendar View
                if 'inpatient_schedule_df' in st.session_state and not st.session_state.inpatient_schedule_df.empty:
                    import utils
                    cal_df = utils.create_inpatient_calendar_df(st.session_state.inpatient_schedule_df)
                    cal_df.to_excel(writer, sheet_name='Inpatient Calendar', index=False)

                # 5. Statistics
                # Aggregate all stats into one sheet or multiple
                # Let's create a 'Statistics' sheet with multiple tables spaced out
                stats_sheet = writer.book.add_worksheet('Statistics')
                row_cursor = 0
                
                # Helper to write df to sheet
                def write_df_to_stats(df, title, start_row):
                    stats_sheet.write(start_row, 0, title)
                    # Write header
                    for col_num, value in enumerate(df.columns.values):
                        stats_sheet.write(start_row + 1, col_num, value)
                    # Write data
                    for row_num, row_data in enumerate(df.values):
                        for col_num, value in enumerate(row_data):
                            stats_sheet.write(start_row + 2 + row_num, col_num, value)
                    return start_row + len(df) + 4 # Space for next table
                
                # Call Stats
                if 'call_schedule_df' in st.session_state:
                    c_counts = st.session_state.call_schedule_df["Resident"].value_counts().reset_index()
                    c_counts.columns = ["Resident", "Call Weeks"]
                    row_cursor = write_df_to_stats(c_counts, "Call Schedule Stats", row_cursor)
                    
                # Inpatient Stats
                if 'inpatient_schedule_df' in st.session_state:
                    i_counts = st.session_state.inpatient_schedule_df["Resident"].value_counts().reset_index()
                    i_counts.columns = ["Resident", "Inpatient Days"]
                    row_cursor = write_df_to_stats(i_counts, "Inpatient Schedule Stats", row_cursor)
                    
                # Coverage Stats
                if 'coverage_stats' in st.session_state:
                     row_cursor = write_df_to_stats(st.session_state.coverage_stats, "Cross Coverage Stats", row_cursor)
                     
                
            st.download_button(
                label="Download Excel File",
                data=buffer,
                file_name=f"Residency_Schedule_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.ms-excel"
            )

    with col_ex2:
        st.subheader("Import State")
        uploaded_state = st.file_uploader("Upload Previous Excel Export", type="xlsx")
        if uploaded_state:
            if st.button("Load State from Excel"):
                try:
                    # Load all sheets
                    xls = pd.ExcelFile(uploaded_state)
                    
                    # Residents
                    if 'Residents' in xls.sheet_names:
                        st.session_state.residents_df = pd.read_excel(xls, 'Residents')
                        st.success("Loaded Residents")
                    
                    # Attendings
                    if 'Attendings' in xls.sheet_names:
                        st.session_state.attendings_df = pd.read_excel(xls, 'Attendings')
                        st.success("Loaded Attendings")
                        
                    # Blocks
                    if 'Blocks' in xls.sheet_names:
                        st.session_state.blocks_df = pd.read_excel(xls, 'Blocks')
                        # Ensure dates are dates
                        st.session_state.blocks_df["Start Date"] = pd.to_datetime(st.session_state.blocks_df["Start Date"]).dt.date
                        st.session_state.blocks_df["End Date"] = pd.to_datetime(st.session_state.blocks_df["End Date"]).dt.date
                        st.success("Loaded Blocks")
                        
                    # Assignments
                    if 'Block Assignments' in xls.sheet_names:
                        df_assign = pd.read_excel(xls, 'Block Assignments', index_col=0)
                        df_assign = df_assign.where(pd.notna(df_assign), None)
                        
                        import re
                        new_cols = []
                        for c in df_assign.columns:
                            c_clean = re.sub(r'\s*\(\d{2}/\d{2}/\d{4} - \d{2}/\d{2}/\d{4}\)$', '', str(c))
                            new_cols.append(c_clean)
                        df_assign.columns = new_cols
                        
                        st.session_state.block_assignments = df_assign
                        st.success("Loaded Block Assignments")
                        
                    # Vacations
                    if 'Vacations' in xls.sheet_names:
                        st.session_state.vacations_df = pd.read_excel(xls, 'Vacations')
                        st.success("Loaded Vacations")
                        
                    # Lectures
                    if 'Lectures' in xls.sheet_names:
                        st.session_state.lectures_df = pd.read_excel(xls, 'Lectures')
                        st.session_state.lectures_df["Date"] = pd.to_datetime(st.session_state.lectures_df["Date"]).dt.date
                        st.success("Loaded Lectures")
                        
                    # Call Schedule
                    if 'Call Schedule' in xls.sheet_names:
                        df_call = pd.read_excel(xls, 'Call Schedule')
                        st.session_state.call_schedule_df = df_call.where(pd.notna(df_call), None)
                        st.success("Loaded Call Schedule")
                        
                    # Inpatient
                    if 'Inpatient Schedule' in xls.sheet_names:
                        df_inpatient = pd.read_excel(xls, 'Inpatient Schedule')
                        st.session_state.inpatient_schedule_df = df_inpatient.where(pd.notna(df_inpatient), None)
                        st.success("Loaded Inpatient Schedule")
                        
                    st.rerun()
                except Exception as e:
                    st.error(f"Error loading state: {e}")

    # Weekly Email Text
    st.divider()
    st.subheader("Weekly Email Text Generator")
    
    col_em1, col_em2 = st.columns([1, 2])

    with col_em1:
        st.write("Select a week to generate the email announcement.")
        if 'call_schedule_df' in st.session_state and not st.session_state.call_schedule_df.empty:
            weeks = sorted(st.session_state.call_schedule_df["Week Start"].unique())
            selected_week_start = st.selectbox("Select Week Start", weeks, key="email_week_select")
            
            if st.button("Generate Email Text"):
                st.session_state.email_gen = True

    with col_em2:
        if 'call_schedule_df' in st.session_state and not st.session_state.call_schedule_df.empty:
             if 'email_gen' in st.session_state and st.session_state.email_gen:
                if selected_week_start:
                    week_row = st.session_state.call_schedule_df[st.session_state.call_schedule_df["Week Start"] == selected_week_start].iloc[0]
                    call_resident = week_row["Resident"]
                    call_attending = week_row["Attending"] if "Attending" in week_row else "Unassigned"
                    week_end = week_row["Week End"]
                    
                    
                    # 1. Dates of Call
                    # "Week of..." is selected_week_start
                    # Calculate Sunday
                    w_start_dt = pd.to_datetime(selected_week_start)
                    w_end_dt = pd.to_datetime(week_end)
                    call_dates_str = f"{w_start_dt.strftime('%m/%d')} - {w_end_dt.strftime('%m/%d')}"
                    
                    # 2. Daily Inpatient Schedule
                    inpatient_daily_text = ""
                    if 'inpatient_schedule_df' in st.session_state and not st.session_state.inpatient_schedule_df.empty:
                         # Filter for Mon-Fri of this week
                         mask = (pd.to_datetime(st.session_state.inpatient_schedule_df["Date"]) >= w_start_dt) & \
                                (pd.to_datetime(st.session_state.inpatient_schedule_df["Date"]) <= w_end_dt)
                         inp_week = st.session_state.inpatient_schedule_df[mask].sort_values("Date")
                         
                         for _, row in inp_week.iterrows():
                             d_str = pd.to_datetime(row["Date"]).strftime("%A %m/%d")
                             r_name = row["Resident"]
                             inpatient_daily_text += f"{d_str}: {r_name}\n"
                    
                    if not inpatient_daily_text:
                        inpatient_daily_text = "None scheduled."

                    # 3. Residents on Vacation
                    vacation_text = ""
                    if 'vacations_df' in st.session_state and not st.session_state.vacations_df.empty:
                        # Check overlaps with this week
                        active_vacations = []
                        for _, v_row in st.session_state.vacations_df.iterrows():
                             # If vacation overlaps with week window
                             v_s = pd.to_datetime(v_row["Start Date"])
                             v_e = pd.to_datetime(v_row["End Date"])
                             
                             if max(v_s, w_start_dt) <= min(v_e, w_end_dt):
                                 active_vacations.append(v_row["Resident"])
                        
                        if active_vacations:
                            vacation_text = ", ".join(sorted(list(set(active_vacations))))
                        else:
                            vacation_text = "None"
                    
                    # 4. Cross Coverage
                    coverage_text = ""
                    if 'coverage_df' in st.session_state and not st.session_state.coverage_df.empty:
                        # Filter for this week
                        mask = (pd.to_datetime(st.session_state.coverage_df["Date"]) >= w_start_dt) & \
                               (pd.to_datetime(st.session_state.coverage_df["Date"]) <= w_end_dt)
                        cov_week = st.session_state.coverage_df[mask].sort_values("Date")
                        
                        for _, row in cov_week.iterrows():
                            d_str = pd.to_datetime(row["Date"]).strftime("%A %m/%d")
                            cov_res = row["Covering Resident"]
                            att_needed = row["Attending Needed"]
                            away_res = row["Resident Away"]
                            coverage_text += f"{d_str}: {cov_res} covering {att_needed} (for {away_res})\n"
                            
                    if not coverage_text:
                        coverage_text = "None."


                    # 5. Lectures
                    lecture_text = ""
                    if 'lectures_df' in st.session_state and not st.session_state.lectures_df.empty:
                        l_mask = (pd.to_datetime(st.session_state.lectures_df["Date"]) >= w_start_dt) & \
                                 (pd.to_datetime(st.session_state.lectures_df["Date"]) <= w_end_dt)
                        lec_week = st.session_state.lectures_df[l_mask].sort_values("Date")
                        
                        if not lec_week.empty:
                            lec_unit = lec_week.iloc[0]["Unit"]
                            lecture_text += f"EDUCATION/EVENTS: {lec_unit}\n"
                            for _, r in lec_week.iterrows():
                                ld_str = pd.to_datetime(r["Date"]).strftime("%A")
                                slot = r["Time Slot"]
                                topic = r["Topic/Speaker"]
                                lecture_text += f"{ld_str} {slot}: {topic}\n"
                        else:
                            lecture_text = "EDUCATION/EVENTS:\nNone scheduled.\n"
                    else:
                        lecture_text = "EDUCATION/EVENTS:\nNone scheduled.\n"


                    email_body = f"""RESIDENT SCHEDULE WEEK OF {w_start_dt.strftime('%m/%d/%y')}

CALL ({call_dates_str}):
Resident: {call_resident}
Attending: {call_attending}

INPATIENT:
{inpatient_daily_text}

CROSS COVERAGE:
{coverage_text}

RESIDENTS ON VACATION:
{vacation_text}

{lecture_text}
CLINIC:
(Refer to Block Schedule)
"""
                    st.text_area("Email Content", value=email_body, height=300)
                    
                    import urllib.parse
                    encoded_body = urllib.parse.quote(email_body)
                    mailto_link = f"mailto:?subject=Resident Schedule: Week of {w_start_dt.strftime('%m/%d/%y')}&body={encoded_body}"
                    st.markdown(f'<a href="{mailto_link}" target="_blank"><button style="padding:0.5rem 1rem; border-radius:4px; border:none; background-color:#FF4B4B; color:white; font-weight:bold; cursor:pointer;">📧 Open in Default Email Client</button></a>', unsafe_allow_html=True)
    
        else:
            st.info("Generate a Call Schedule first.")
