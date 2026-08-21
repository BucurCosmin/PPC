# Modification: POC Power Factor Closed-Loop PI Control

**Feature:** `VArControl_Mode = 4` — POC PF tracking via PI integrator  
**Date:** 2026-08-18  
**Status:** Planned — not yet applied to PLC  

---

## Problem Statement

The plant inverters are connected via MV cables and an MV/HV transformer to the Point of Connection (POC). Cable and transformer reactive consumption varies with voltage and load. If PF is controlled at the inverter level, the PF at POC drifts depending on operating conditions. The goal is to close the loop at POC using the actual Q measured there.

---

## Architecture

```
Inverters (MV)  →  MV cables  →  MV/HV transformer  →  POC (HV)
   ↑ WSpt/VArSpt                                          ↑ P_poc, Q_poc measured
   |                                                      |
   └─────────── PI controller closes loop here ───────────┘
```

**Control law:**
```
Q_poc_required = P_poc × tan(arccos(|PF_target|)) × sign(PF_target)
Q_error        = Q_poc_required − Q_poc_measured
Q_cmd (integrator) += Ki × Q_error × dt
```
The integrator naturally absorbs cable + transformer reactive losses — no cable model needed.

---

## Sign Convention

**IMPORTANT — verify with actual grid meter before commissioning:**

- `Q_poc_kVAr` positive = plant is **underexcited / inductive** (absorbing vars from grid)  
- `Q_poc_kVAr` negative = plant is **overexcited / capacitive** (injecting vars into grid)  
- `PF_poc_target` positive = **overexcited** (capacitive, injecting vars)  
- `PF_poc_target` negative = **underexcited** (inductive, absorbing vars)  

This matches the existing convention in `FB_PPC_QCapability` where:
> "positive Q = inductive (absorb vars)"

---

## Files to Modify

| File | Changes |
|---|---|
| `FC_PPC_ReactiveControl.scl` | Mode 2 fix: replace PFCtlCom with PF→Q dispatch using Wactive |
| `FB_PPC_QCapability.scl` | New inputs, static var, outputs, Mode 4 CASE block |
| `FB_PPC_Controller.scl` | New inputs, pass to QCap call, mirror diagnostics |
| `FC_PPC_InitData.scl` | Initialize new PPC_Controller DB fields |
| `PPC_Controller` DB (TIA Portal only) | Add new SCADA-writable and diagnostic fields |
| OB30 (TIA Portal only) | Wire `P_poc_kW` / `Q_poc_kVAr` at FB_PPC_Controller call site |

`FC_PPC_PowerDistribution.scl` is **not modified**.

---

## 0. FC_PPC_ReactiveControl.scl — Mode 2 Fix (prerequisite)

**Problem:** `VArMode = 1075` (PFCtlCom) causes inverter errors on this hardware.  
**Fix:** Compute Q from PF and actual measured P (`Wactive`) in the PLC, dispatch as `VArSpt + VArCtlCom`.

Replace the entire Mode 2 CASE block:

**Remove (old):**
```scl
2:  // ── Mode 2: PF setpoint ──────────────────────────────────────────────
    IF #Sim_Mode THEN
        ...sim calculation using WSpt...
        #Inverters[#i].VArMode := 1072;   // VArCtlCom — Q dispatch in sim
    ELSE
        // Real mode: send PF setpoint
        #Inverters[#i].VArSpt  := 0;
        IF ABS(#Targets_PF) > 0.1 THEN
            #Inverters[#i].PFSpt := REAL_TO_DINT(#Targets_PF * 10000.0);
        ELSE
            #Inverters[#i].PFSpt := 10000;   // Unity PF safe default
        END_IF;
        #Inverters[#i].VArMode := 1075;   // PFCtlCom
    END_IF;
```

**Replace with (new):**
```scl
// [CHANGED MOD_PF_Dispatch] Mode 2 rewritten: removed Sim_Mode/PFCtlCom branch,
// always computes Q from Wactive and dispatches as VArCtlCom.
2:  // Mode 2: PF->Q dispatch
    // PFCtlCom (VArMode=1075) not used - causes inverter errors.
    // Compute Q = P x tan(arccos(|PF|)) from actual measured Wactive,
    // clamp to SMA physical envelope, write as VArSpt + VArCtlCom.
    // Uses Wactive (not WSpt) so Q tracks actual P, not commanded P.
    // Sign: negative Targets_PF = lagging (inductive, absorb vars).
    #PF_abs := ABS(#Targets_PF);
    IF #PF_abs > 0.1 AND #PF_abs <= 1.0 THEN
        #tan_phi := SQRT(1.0 - #PF_abs * #PF_abs) / #PF_abs;
        #Q_sim   := DINT_TO_REAL(#Inverters[#i].Wactive) * #tan_phi;   // [CHANGED] was WSpt
        IF #Targets_PF < 0.0 THEN #Q_sim := -#Q_sim; END_IF;
    ELSE
        #Q_sim := 0.0;
    END_IF;
    // SMA physical envelope clamp - prevents Q exceeding apparent power limit.
    "FC_SMA_QEnvelope"(
        P_kW      := DINT_TO_REAL(#Inverters[#i].Wactive),   // [CHANGED] was WSpt
        U_pu      := #U_pu,
        Qmax_kVar => #Qmax_inv
    );
    IF #Q_sim >  #Qmax_inv THEN #Q_sim :=  #Qmax_inv; END_IF;
    IF #Q_sim < -#Qmax_inv THEN #Q_sim := -#Qmax_inv; END_IF;
    #Inverters[#i].VArSpt  := REAL_TO_DINT(#Q_sim);
    #Inverters[#i].PFSpt   := 0;
    #Inverters[#i].VArMode := 1072;   // VArCtlCom   [CHANGED] was 1075 PFCtlCom
```

**Note:** `Sim_Mode` input remains declared but is now unused in Mode 2 — TIA Portal may warn, harmless.

---

## 1. PPC_Controller DB (DB39) — New Fields

Add to the DB in TIA Portal. All are SCADA-writable except the diagnostics.

### SCADA-writable (operator/SCADA sets these)

| Field | Type | Default | Description |
|---|---|---|---|
| `PF_poc_target` | REAL | `1.0` | Target PF at POC. Signed: `+0.95` = overexcited (inject vars), `-0.95` = underexcited (absorb vars) |
| `PF_Kp` | REAL | `0.0` | Proportional gain kVAr/kVAr. Start at 0 (pure integrator) |
| `PF_Ki` | REAL | `50.0` | Integral gain kVAr/(kVAr·s). Tune on site — start very small |
| `PF_Tt` | REAL | `5.0` | Anti-windup tracking time constant (seconds). 0 = disable anti-windup |
| `PF_Reset` | BOOL | `FALSE` | One-shot: TRUE resets PF integrator this scan then self-clears |

### SCADA-readable diagnostics

| Field | Type | Description |
|---|---|---|
| `Q_poc_required` | REAL | kVAr target Q at POC computed from P_poc and PF_poc_target |
| `Q_poc_error` | REAL | kVAr Q error (Q_poc_required − Q_poc_measured) |
| `PF_poc_actual` | REAL | Actual PF at POC computed from P_poc and Q_poc (unsigned, 0–1) |

---

## 2. FB_PPC_QCapability.scl

### 2a. VAR_INPUT — add at end of VAR_INPUT block

```scl
// [ADDED MOD_POC_PF] Mode 4 inputs — add after existing VAR_INPUT declarations
P_poc_kW      : REAL;   // kW, active power measured at POC (grid meter)
Q_poc_kVAr    : REAL;   // kVAr, reactive power measured at POC (grid meter)
                         //   positive = inductive (plant absorbs vars)
                         //   negative = capacitive (plant injects vars)
PF_poc_target : REAL;   // Target PF at POC. Signed: + overexcited, - underexcited.
PF_Kp         : REAL;   // kVAr/kVAr proportional gain (start at 0.0 - pure integrator)
PF_Ki         : REAL;   // kVAr/(kVAr·s) integral gain (start small, tune on site)
PF_Tt         : REAL;   // s, anti-windup tracking time constant (0 = disable)
PF_Reset      : BOOL;   // TRUE = reset PF integrator this scan (one-shot from DB)
```

### 2b. VAR_OUTPUT — add at end of VAR_OUTPUT block

```scl
// [ADDED MOD_POC_PF] Mode 4 diagnostic outputs — add after existing VAR_OUTPUT declarations
Q_poc_required : REAL;   // kVAr, target Q at POC — diagnostic
Q_poc_error    : REAL;   // kVAr, Q error at POC — diagnostic
PF_poc_actual  : REAL;   // actual PF at POC (unsigned 0-1) — diagnostic
```

### 2c. VAR (static) — add one line

```scl
PF_I : REAL := 0.0;   // kVAr, Mode 4 POC PF PI integrator accumulator   // [ADDED MOD_POC_PF]
```

### 2d. VAR_TEMP — add at end

```scl
// [ADDED MOD_POC_PF] Mode 4 temp vars — add after existing VAR_TEMP declarations
PF_abs    : REAL;   // |PF_poc_target|
S_poc     : REAL;   // kVA, apparent power at POC
Q_poc_req : REAL;   // kVAr, required Q at POC
Q_err_pf  : REAL;   // kVAr, Q error for PF controller
PF_unsat  : REAL;   // kVAr, PI output before capability saturation clamp
```

### 2e. Reset block — extend existing reset (around line 172)

Existing code:
```scl
IF #Plant_Mode = 2 OR (#N_Online = 0 AND #Control_Mode = 3) OR #PID_Reset THEN
    #PID_I       := 0.0;
    #PID_D_filt  := 0.0;
    #U_meas_prev := #U_meas;
END_IF;
```

Add Mode 4 integrator reset **after** the existing block:
```scl
// [ADDED MOD_POC_PF] Mode 4 (POC PF PI) integrator reset
IF #Plant_Mode = 2 OR #PF_Reset THEN
    #PF_I := 0.0;
END_IF;
```

### 2f. Bumpless transfer block — extend existing (around line 180)

Existing code handles transitions into/out of Mode 3. Add Mode 4 handling **inside the same IF block**:

```scl
IF #Control_Mode <> #Ctrl_Mode_prv THEN
    IF #Control_Mode = 3 THEN
        // existing bumpless INTO mode 3 — unchanged
        #PID_I      := #Ramps_Qcmd - #U_Kp * (#U_meas - #U_setpoint_ext);
        #PID_D_filt := 0.0;
    ELSIF #Control_Mode = 4 THEN   // [ADDED MOD_POC_PF]
        // Bumpless transfer INTO mode 4:
        // Pre-load integrator so first PI output = current ramp state - no Q jump.
        #PF_I       := #Ramps_Qcmd;   // [ADDED MOD_POC_PF]
    ELSE
        // existing: switching away from mode 3 - reset PID state — unchanged
        #PID_I      := 0.0;
        #PID_D_filt := 0.0;
        // Also reset Mode 4 integrator when leaving it   // [ADDED MOD_POC_PF]
        IF #Ctrl_Mode_prv = 4 THEN   // [ADDED MOD_POC_PF]
            #PF_I := 0.0;             // [ADDED MOD_POC_PF]
        END_IF;                        // [ADDED MOD_POC_PF]
    END_IF;
    #U_meas_prev := #U_meas;
END_IF;
#Ctrl_Mode_prv := #Control_Mode;
```

### 2g. CASE block — add Mode 4 before the ELSE branch

Insert after the closing of Mode 3 (`3: ... END`) and before `ELSE   // Mode 2 (Off) or unknown`:

```scl
// [ADDED MOD_POC_PF] entire Mode 4 block — insert before the ELSE branch
4:  // Mode 4: POC PF closed-loop PI
    // Q_poc_required = P_poc × tan(arccos(|PF_target|)) × sign(PF_target)
    // Q_error = Q_poc_required − Q_poc_measured
    // PI integrator → Q_cmd_inverters
    // Cable + transformer reactive compensation is automatic (closed loop).
    // Sign: PF_poc_target positive = overexcited (inject vars) = positive Q_poc_required.
    //       Convention here matches system: positive Q = inductive (absorb).
    //       Overexcited = negative Q → PF_poc_target positive → Q_poc_req negative.
    #PF_abs := ABS(#PF_poc_target);
    IF #PF_abs > 0.1 AND #PF_abs <= 1.0 AND #P_poc_kW > 0.0 THEN
        #Q_poc_req := -(#P_poc_kW * SQRT(1.0 - #PF_abs * #PF_abs) / #PF_abs);
        IF #PF_poc_target < 0.0 THEN #Q_poc_req := -#Q_poc_req; END_IF;
    ELSE
        #Q_poc_req := 0.0;
    END_IF;

    // Q error: positive error = plant producing too little capacitive Q (or too much inductive)
    #Q_err_pf := #Q_poc_req - #Q_poc_kVAr;

    // PI output (unsaturated)
    #PF_unsat := #PF_Kp * #Q_err_pf + #PF_I;

    // Saturate to Stage 1 P-Q capability limits
    IF #PF_unsat > #Q_cap_interp THEN
        #Q_command := #Q_cap_interp;
    ELSIF #PF_unsat < -#Q_ind_interp THEN
        #Q_command := -#Q_ind_interp;
    ELSE
        #Q_command := #PF_unsat;
    END_IF;

    // Anti-windup: back-calculation (same structure as Mode 3)
    IF #PF_Tt > 0.0 THEN
        #PF_I := #PF_I
               + #PF_Ki * #Q_err_pf * #CycleTime_s
               + (#CycleTime_s / #PF_Tt) * (#Q_command - #PF_unsat);
    ELSE
        #PF_I := #PF_I + #PF_Ki * #Q_err_pf * #CycleTime_s;
    END_IF;

    // Diagnostic outputs
    #Q_poc_required := #Q_poc_req;
    #Q_poc_error    := #Q_err_pf;
    IF #P_poc_kW > 0.0 THEN
        #S_poc := SQRT(#P_poc_kW * #P_poc_kW + #Q_poc_kVAr * #Q_poc_kVAr);
        IF #S_poc > 0.0 THEN
            #PF_poc_actual := #P_poc_kW / #S_poc;
        ELSE
            #PF_poc_actual := 1.0;
        END_IF;
    ELSE
        #PF_poc_actual := 0.0;
    END_IF;
```

### 2h. Q ramp bypass block — extend existing (around line 297)

Existing code:
```scl
IF #Control_Mode = 3 THEN
    #Ramps_Qcmd := #Q_command;
END_IF;
```

Change to:
```scl
// Mode 3 and Mode 4: integrator already rate-limits Q - bypass external ramp.
// Ramps_Qcmd tracks output for bumpless handover to modes 0/1.
IF #Control_Mode = 3 OR #Control_Mode = 4 THEN   // [CHANGED MOD_POC_PF] added OR #Control_Mode = 4
    #Ramps_Qcmd := #Q_command;
END_IF;
```

---

## 3. FB_PPC_Controller.scl

### 3a. VAR_INPUT — add two inputs

```scl
// [ADDED MOD_POC_PF] add after existing VAR_INPUT declarations
P_poc_kW   : REAL;   // kW, active power at POC from grid meter (wired in OB30)
Q_poc_kVAr : REAL;   // kVAr, reactive power at POC from grid meter (wired in OB30)
                      //   positive = plant absorbing (inductive/underexcited)
                      //   negative = plant injecting (capacitive/overexcited)
```

### 3b. QCap_IDB call — add new parameters

In the `#QCap_IDB(...)` call (step ⑤), add after the existing `PID_Reset` line:

```scl
P_poc_kW      := #P_poc_kW,           // [ADDED MOD_POC_PF]
Q_poc_kVAr    := #Q_poc_kVAr,         // [ADDED MOD_POC_PF]
PF_poc_target := "PPC_Controller".PF_poc_target,   // [ADDED MOD_POC_PF]
PF_Kp         := "PPC_Controller".PF_Kp,           // [ADDED MOD_POC_PF]
PF_Ki         := "PPC_Controller".PF_Ki,           // [ADDED MOD_POC_PF]
PF_Tt         := "PPC_Controller".PF_Tt,           // [ADDED MOD_POC_PF]
PF_Reset      := "PPC_Controller".PF_Reset,        // [ADDED MOD_POC_PF]
```

### 3c. After QCap_IDB call — mirror diagnostics and clear PF_Reset

After the existing diagnostic mirror block (after `"PPC_Controller".PID_active := ...`), add:

```scl
// [ADDED MOD_POC_PF] Mode 4 POC PF diagnostics
"PPC_Controller".Q_poc_required := #QCap_IDB.Q_poc_required;
"PPC_Controller".Q_poc_error    := #QCap_IDB.Q_poc_error;
"PPC_Controller".PF_poc_actual  := #QCap_IDB.PF_poc_actual;
"PPC_Controller".PF_Reset       := FALSE;   // clear one-shot after FB processed it
```

### 3d. OB30 wiring

In OB30, wire the FB_PPC_Controller call:

```scl
"FB_PPC_Controller"(
    ...existing inputs...,
    P_poc_kW   := "GridMeter".P_kW,     // ← wire from grid meter DB tag
    Q_poc_kVAr := "GridMeter".Q_kVAr,   // ← wire from grid meter DB tag (check sign!)
    ...
);
```

---

## 4. FC_PPC_InitData.scl

Add to the reactive power section (after existing Q ramp rate lines):

```scl
// [ADDED MOD_POC_PF] Mode 4 POC PF PI defaults
"PPC_Controller".PF_poc_target := 1.0;    // unity PF - safe initial default
"PPC_Controller".PF_Kp         := 0.0;    // pure integrator to start
"PPC_Controller".PF_Ki         := 50.0;   // kVAr/(kVAr·s) - tune slowly on site
"PPC_Controller".PF_Tt         := 5.0;    // s, anti-windup time constant
// Reset PF integrator on startup / defaults reset
"FB_PPC_Controller_DB".QCap_IDB.PF_I := 0.0;
```

---

## 5. Activation

**Mode 4 — POC PF closed-loop (track PF at POC):**
```
"PPC_Controller".VArControl_Mode := 4   // selects Mode 4 in QCapability
Cmd_VArMode := 1                         // ReactiveControl stays in Q dispatch (Mode 1)
```

**Mode 5 — POC Q closed-loop (track Q setpoint at POC, same as Cmd_Q but feedback-corrected):**
```
"PPC_Controller".VArControl_Mode := 5
Cmd_VArMode := 1
```

Mode 5 uses the same `PF_Kp`, `PF_Ki`, `PF_Tt`, `PF_I`, and diagnostic outputs as Mode 4.
The only difference: target Q = `Cmd_Q` directly instead of being derived from `PF_poc_target` and `P_poc`.

`Cmd_VArMode` must remain `1` (VArCtlCom) for both modes — output flows through the existing
Q ramp → Q capability → ReactiveControl Mode 1 path. `Cmd_VArMode = 2` (PF mode) must not be
used simultaneously.

---

## 6. Tuning Guide (commissioning)

1. **Start:** `PF_Kp = 0.0`, `PF_Ki = 50.0`, `PF_Tt = 5.0`
2. **Observe** `Q_poc_error` and `PF_poc_actual` on HMI
3. **If response too slow:** increase `PF_Ki` in steps (×2 each time)
4. **If oscillating:** reduce `PF_Ki` (÷2) or increase `PF_Tt`
5. **After stable:** optionally add small `PF_Kp` (e.g. 10–50) for faster initial response
6. `PF_Tt = 5.0 s` is the anti-windup time constant — leave unless oscillation is severe

---

## 7. Sign Convention Verification (before commissioning)

Before going live, verify in watch table with plant at known operating point:

| Condition | Expected `Q_poc_kVAr` sign |
|---|---|
| Plant injecting capacitive vars (overexcited) | Negative |
| Plant absorbing inductive vars (underexcited) | Positive |
| Plant at unity PF | ~0 |

If signs are reversed on the grid meter, negate `Q_poc_kVAr` at the OB30 wiring point.
