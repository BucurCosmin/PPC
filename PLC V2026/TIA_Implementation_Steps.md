# TIA Portal Implementation Steps

Changes to apply from `PLC V2026\` folder.  
**Estimated time:** 30–45 min  
**Risk:** Medium — download requires brief PLC stop or FALLBACK mode.

---

## Before you start

1. **Back up the TIA project** — File → Save as → new name with today's date.
2. **Go online** and note current `"PPC_Controller".VArControl_Mode` — you will restore it after download.
3. Put the plant in **FALLBACK** or ensure `EN_PPC = FALSE` before downloading code blocks.

---

## Step 1 — Add new fields to PPC_Controller DB (DB39)

These are the SCADA-writable parameters and diagnostic outputs for Mode 4 and 5.  
DB39 uses optimised access (`S7_Optimized_Access = TRUE`) so order does not matter.

In TIA Portal:
1. Open **Project tree → PLC → Program blocks → PPC_Controller [DB39]**
2. Click **Add new row** at the bottom of the variable table for each field below:

### SCADA-writable (operator/SCADA sets these)

| Name | Data type | Start value | Comment |
|---|---|---|---|
| `PF_poc_target` | Real | `1.0` | Target PF at POC. +0.95 = overexcited (inject vars), -0.95 = underexcited (absorb) |
| `PF_Kp` | Real | `0.0` | Proportional gain kVAr/kVAr — start at 0 (pure integrator) |
| `PF_Ki` | Real | `0.05` | Integral gain (1/s) — start at 0.05 (~30s settling); Ki=50 causes oscillation |
| `PF_Tt` | Real | `5.0` | Anti-windup time constant seconds — 0 disables anti-windup |
| `PF_Reset` | Bool | `FALSE` | One-shot: write TRUE to reset PI integrator, clears automatically next cycle |

### Diagnostics (SCADA reads these)

| Name | Data type | Start value | Comment |
|---|---|---|---|
| `Q_poc_required` | Real | `0.0` | Target Q at POC computed from P and PF target (kVAr) |
| `Q_poc_error` | Real | `0.0` | Q error at POC: required − measured (kVAr) |
| `PF_poc_actual` | Real | `0.0` | Actual PF at POC computed from P and Q measurements (0–1) |

3. **Compile DB39:** Right-click DB39 → **Compile → Software (rebuild all)**.  
4. Download DB39 now (can be done online without stopping): Right-click → **Download to device → Software**.  
   TIA will warn about data inconsistency — choose **Stop module** if asked, or use **Load to device without reinitialization** if available to keep existing values.

> **Note:** Adding fields to an optimised DB with running PLC is safe — existing fields keep their values.

---

## Step 2 — Update FB_PPC_QCapability

This FB has the largest changes: new VAR blocks and Mode 4/5 logic.  
**Do this before FB_PPC_Controller** — the controller calls this FB and depends on its interface.

1. Open **Project tree → PLC → Program blocks → FB_PPC_QCapability**.
2. Click inside the code editor, press **Ctrl+A** to select all.
3. Open `PLC V2026\FB_PPC_QCapability.scl` in Notepad or VS Code.
4. Select all (Ctrl+A), copy (Ctrl+C).
5. Back in TIA Portal — paste (Ctrl+V). The entire block is replaced.
6. Click **Compile** (the compile button in the toolbar, or F7).  
   Expected: 0 errors. If warnings about unused inputs appear — harmless.

### What changed (search for `[ADDED` to find all changes):
- 7 new VAR_INPUT (P_poc_kW, Q_poc_kVAr, PF_poc_target, PF_Kp, PF_Ki, PF_Tt, PF_Reset)
- 3 new VAR_OUTPUT (Q_poc_required, Q_poc_error, PF_poc_actual)
- 1 new VAR static (PF_I — PI integrator for Mode 4/5)
- 5 new VAR_TEMP (PF_abs, S_poc, Q_poc_req, Q_err_pf, PF_unsat)
- PF_I reset block after existing PID reset
- Bumpless transfer extended for Mode 4 and 5
- Mode 4 CASE block (POC PF PI)
- Mode 5 CASE block (POC Q PI)
- Ramp bypass extended to include Mode 4 and 5

---

## Step 3 — Update FB_PPC_Controller

1. Open **Project tree → PLC → Program blocks → FB_PPC_Controller**.
2. Ctrl+A → delete → paste content of `PLC V2026\FB_PPC_Controller.scl`.
3. Compile (F7). Expected: 0 errors.

### What changed:
- 2 new VAR_INPUT (P_poc_kW, Q_poc_kVAr)
- QCap_IDB call: 7 new parameters added, comma added after PID_Reset
- 4 new lines mirroring Mode 4/5 diagnostics to DB39 after the QCap call
- PF_Reset cleared after QCap call (one-shot pattern)

---

## Step 4 — Update FC_PPC_ReactiveControl

1. Open **Project tree → PLC → Program blocks → FC_PPC_ReactiveControl**.
2. Ctrl+A → delete → paste content of `PLC V2026\FC_PPC_ReactiveControl.scl`.
3. Compile (F7). Expected: 0 errors, possibly 1 warning (Sim_Mode unused in Mode 2 — harmless).

### What changed:
- Mode 2 rewritten: removed Sim_Mode/PFCtlCom branch
- Now always computes Q from Wactive (not WSpt) and writes as VArCtlCom (not PFCtlCom)
- VArMode changed from 1075 to 1072

---

## Step 5 — Update FC_PPC_InitData

1. Open **Project tree → PLC → Program blocks → FC_PPC_InitData**.
2. Ctrl+A → delete → paste content of `PLC V2026\FC_PPC_InitData.scl`.
3. Compile (F7). Expected: 0 errors.

### What changed:
- 5 new lines initialising PF_poc_target, PF_Kp, PF_Ki, PF_Tt, and PF_I

---

## Step 6 — Wire OB30 (FB_PPC_Controller call site)

1. Open **Project tree → PLC → Program blocks → OB30**.
2. Find the `FB_PPC_Controller` call block (the yellow call box in LAD/FBD, or the call in SCL).
3. Add the two new input wires:

| FB input | Wire to | Comment |
|---|---|---|
| `P_poc_kW` | `"GridMeter".P_kW` | Replace `"GridMeter"` with your actual grid meter DB name |
| `Q_poc_kVAr` | `"GridMeter".Q_kVAr` | Check sign — see note below |

> **Sign check for Q_poc_kVAr:**  
> The convention used in the PLC is: **positive = plant absorbing vars (inductive/underexcited)**.  
> Go online with the plant running at known PF. If your meter reads Q negative when the plant is  
> absorbing, negate at the wiring point: `Q_poc_kVAr := -"GridMeter".Q_kVAr`.

4. Compile OB30 (F7). Expected: 0 errors.

> **Tip:** The grid meter DB tag for `P_actual_kW` (already wired to FB_PPC_Controller) comes from  
> the same meter — check what DB that tag lives in and use the same DB for `Q_poc_kVAr`.

---

## Step 7 — Full compile

1. In the project tree, right-click the **PLC** node.
2. Select **Compile → Software (rebuild all)**.
3. Resolve any errors before proceeding. Warnings about unused variables are safe to ignore.

---

## Step 8 — Download to PLC

1. Ensure plant is in **FALLBACK** or `EN_PPC = FALSE`.
2. Click **Download to device** (the download button, or Ctrl+L).
3. In the download dialog:
   - Select **Stop module** if prompted (PLC will stop briefly during download).
   - Check "Consistent download" if available.
4. After download: **Start module**.

> **Important:** The new QCap_IDB fields (`PF_I`, and the new VAR_INPUT defaults) will be  
> initialised to their declared start values (PF_I = 0.0, etc.) on the first download.  
> DB39 new fields will also be at their start values from Step 1.

---

## Step 9 — Initialise defaults

1. Go **Online**.
2. Open a **Watch table**, add: `"PPC_Controller".ResetToDefaults`.
3. Write `TRUE` — this calls `FC_PPC_InitData` once, writing PF_poc_target=1.0, PF_Ki=50.0, etc.  
   The field self-clears to FALSE after one OB30 cycle.

Or alternatively call it from OB100 by doing a **memory reset (MRES)** — but this resets all DB values, so the Watch table approach is safer if the plant has been tuned.

---

## Step 10 — Verify online

Open a Watch table with these tags and confirm correct values:

| Tag | Expected after download | Notes |
|---|---|---|
| `"PPC_Controller".PF_poc_target` | 1.0 | Unity PF default |
| `"PPC_Controller".PF_Ki` | 50.0 | Default gain |
| `"PPC_Controller".PF_Tt` | 5.0 | Anti-windup |
| `"PPC_Controller".Q_poc_required` | updating | Should show ~0 at unity PF |
| `"PPC_Controller".Q_poc_error` | updating | Difference between required and measured |
| `"PPC_Controller".PF_poc_actual` | updating | Actual POC PF (0–1) |
| `"FB_PPC_Controller_DB".QCap_IDB.PF_I` | 0.0 | Integrator — should be 0 at startup |

---

## Step 11 — Activate Mode 4 or 5 (when ready to test)

**Mode 4 — track PF at POC:**
```
"PPC_Controller".VArControl_Mode := 4
Cmd_VArMode := 1   (ensure ReactiveControl is in Q dispatch mode)
"PPC_Controller".PF_poc_target := 0.95   (or target PF)
```

**Mode 5 — track Q setpoint at POC (closed-loop):**
```
"PPC_Controller".VArControl_Mode := 5
Cmd_VArMode := 1
Cmd_Q := <target kVAr>
```

Monitor `Q_poc_error` — should converge to ~0 within 20–60 seconds with default Ki=50.

---

## Rollback

If any issue occurs after download:
1. Write `"PPC_Controller".VArControl_Mode := 0` (Fixed Q, open loop — safe state).
2. Restore the TIA project backup from Step 0 (Before you start).
3. Re-download the previous version.

The Mode 2 (PF dispatch) change to FC_PPC_ReactiveControl is always active regardless of
VArControl_Mode. If inverters show unexpected reactive behaviour in Mode 2, check that
`Cmd_VArMode = 2` is intentional and that `Targets_PF` is set correctly.
