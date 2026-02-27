# Residency Schedule Maker

A Streamlit-based scheduling application designed for Radiation Oncology residency programs. This tool automates the creation of block schedules, call schedules, inpatient coverage, and cross-coverage for vacations.

## Quick Start
1. **Run the App**: Launch the app by running `run_app.bat` or `streamlit run app.py` in your terminal.
2. **Import Data**: On the initial screen, upload your personnel CSV or use the provided `sample resident attending input.csv`. The CSV must contain `Name` and `Role` (Resident / Attending) columns.
3. **Set Dates**: Define the master start and end dates for the academic year.

## Scheduling Workflow

The schedule should generally be built in the following order:

1. **Block Schedule**: 
   - Define your 1-2 month rotation blocks.
   - Assign each resident to an Attending, Satellite (L&M), or Elective rotation for the block. 
   - *Solver Rules*: Ensures each resident has exactly one assignment per block and that Satellite (L&M) is always covered by at least one resident.

2. **Call Schedule**:
   - Generates weekly call assignments.
   - *Solver Rules*: Respects PGY target call weeks based on the configuration. Prevents residents from taking call if they are assigned to Satellite (L&M) or are on Vacation during that week.

3. **Inpatient Schedule**:
   - Generates daily weekday (Monday-Friday) inpatient coverage.
   - *Solver Rules*: Prevents assignment if the resident is on Vacation, on Satellite (L&M), or if their currently assigned Attending for that block has a clinic day on that specific weekday. It also prevents overlap with Cross Coverage assignments.

4. **Vacation Requests**:
   - Add resident vacation dates in this tab. 

5. **Cross Coverage**:
   - Identifies days where an Attending needs coverage because their primary resident is on vacation.
   - *Solver Rules*: Assigns an available resident to cover the Attending's clinic. It prevents taking a resident who is on Vacation, assigned to Satellite (L&M), or already assigned to the Inpatient schedule on that day. It aims to distribute coverage shifts among remaining eligible residents.

6. **Lecture Schedule**:
   - Manage the daily educational lectures and events.
   - Can add, edit, or delete lectures via the provided inputs.

## Important Features

- **Locking Assignments**: For the Block, Inpatient, and Cross Coverage schedules, you can manually lock specific assignments by checking the "Lock" box next to a row (or by leaving the "Lock current assignments" checkbox toggled on). Re-running the auto-generators will respect these locked assignments and only try to fill the remaining unlocked slots.
- **Preventing Overlaps**: The solvers strictly prevent double-booking a resident on both Inpatient and Cross Coverage on the same day. 
- **Export & Import**: You can download the entire scheduling state (including Lecture Schedules) as an Excel file, which acts as a save state. You can upload this Excel file later to resume work or share it with others.
- **Weekly Email Generator**: Go to the Export tab, select a Week, and generate a pre-formatted email text that combines Call, Inpatient, Cross Coverage, Vacation, and Lecture information for easy distribution.
