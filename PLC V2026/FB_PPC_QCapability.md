# FB_PPC_QCapability — Change Log

## Overview

This FB generates the plant-level reactive power command (`Q_setpoint_final`) by:
1. Selecting a Q source from the active control mode (fixed-Q, U-droop, U-PID, POC-PF PI, or POC Q PI)
2. Applying Q ramp rate limiting
3. Clamping to the P-Q capability envelope (ANRE Art. 147/152)
4. Applying the SMA physical envelope (Stage 2 hard limit)

It is called from `FB_PPC_Controller` at step ④, before `FC_PPC_ReactiveControl`.

---

## Why this change was needed

The plant Point of Connection (POC) is at the HV side of the MV/HV transformer. Between the
inverters and the POC there are MV cables and the transformer, both of which consume reactive power.
This reactive consumption varies with voltage and load:

- MV cable capacitive component: `Q_cap ∝ V²` (increases at high voltage)
- MV cable/transformer inductive component: `Q_ind ∝ I² × X` (increases at high current)

If PF is controlled at the inverter level (previous approach), the PF at the POC drifts as
operating conditions change. The grid operator measures and penalises POC PF, not inverter PF.

**Solution:** Close the loop at the POC using a PI integrator on Q error. The integrator naturally
absorbs all cable and transformer reactive losses without requiring a cable model or temperature
corrections. Response is intentionally slow (pure integrator, Ki = 50 kVAr/(kVAr·s)) to avoid
oscillations caused by measurement noise or voltage-dependent cable capacitance.

---

## Changes Applied

All changes are tagged `[ADDED MOD_POC_PF]` in the code.

---

### 1. VAR_INPUT — 7 new inputs added after `PID_Reset`

| Input | Type | Purpose |
|---|---|---|
| `P_poc_kW` | REAL | Active power measured at POC from grid meter (kW) |
| `Q_poc_kVAr` | REAL | Reactive power at POC from grid meter (kVAr). Positive = inductive (plant absorbs), negative = capacitive (plant injects) |
| `PF_poc_target` | REAL | Target PF at POC. Signed: positive = overexcited (inject vars), negative = underexcited (absorb vars) |
| `PF_Kp` | REAL | Proportional gain kVAr/kVAr. Start at 0.0 (pure integrator) |
| `PF_Ki` | REAL | Integral gain kVAr/(kVAr·s). Start small (50), tune on site |
| `PF_Tt` | REAL | Anti-windup tracking time constant (s). 0 = disable anti-windup |
| `PF_Reset` | BOOL | One-shot: TRUE resets PF integrator this scan, then cleared by FB_PPC_Controller |

These are wired at the `QCap_IDB(...)` call in `FB_PPC_Controller` from `"PPC_Controller"` DB fields
and the `P_poc_kW` / `Q_poc_kVAr` inputs of FB_PPC_Controller (wired from grid meter DB in OB30).

---

### 2. VAR_OUTPUT — 3 new diagnostic outputs added after `PID_active`

| Output | Type | Purpose |
|---|---|---|
| `Q_poc_required` | REAL | Target Q at POC computed from P_poc and PF_poc_target (kVAr) |
| `Q_poc_error` | REAL | Q error: Q_poc_required − Q_poc_measured (kVAr) |
| `PF_poc_actual` | REAL | Actual PF at POC computed from P_poc and Q_poc_kVAr (unsigned 0–1) |

These are mirrored to `"PPC_Controller"` DB by `FB_PPC_Controller` after the QCap call, making them
visible on HMI and SCADA for tuning and monitoring.

---

### 3. VAR (static) — `PF_I` added after `Ctrl_Mode_prv`

```
PF_I : Real := 0.0;   // kVAr, Mode 4 POC PF PI integrator accumulator
```

Static (retained between OB30 scans) so the integrator state persists across cycles. Separate from
`PID_I` (Mode 3 U-control integrator) to allow both modes to have independent state.

---

### 4. VAR_TEMP — 5 new temporary variables added after `D_term`

| Variable | Type | Purpose |
|---|---|---|
| `PF_abs` | REAL | `ABS(PF_poc_target)` — avoids calling ABS twice |
| `S_poc` | REAL | Apparent power at POC: `sqrt(P² + Q²)` for PF_poc_actual calculation |
| `Q_poc_req` | REAL | Required Q at POC from PF target and P_poc |
| `Q_err_pf` | REAL | Q error for PI controller: `Q_poc_req - Q_poc_kVAr` |
| `PF_unsat` | REAL | PI output before capability saturation clamp (used in anti-windup) |

---

### 5. Integrator reset block — added after existing PID reset block (line ~196)

```scl
// [ADDED MOD_POC_PF] Mode 4 POC PF PI integrator reset
IF #Plant_Mode = 2 OR #PF_Reset THEN
    #PF_I := 0.0;
END_IF;
```

**Why separate from the PID reset block:**
The existing block resets `PID_I` when `Plant_Mode = 2` OR `N_Online = 0 AND Control_Mode = 3` OR
`PID_Reset`. Mode 4 only resets on FALLBACK or explicit operator command (`PF_Reset`) — not on
`N_Online = 0` (we want the integrator to hold state while inverters restart so the Q command is
ready when they come back online).

---

### 6. Bumpless transfer — extended IF/ELSIF/ELSE block (line ~203)

**Before:**
```scl
IF #Control_Mode <> #Ctrl_Mode_prv THEN
    IF #Control_Mode = 3 THEN
        ...bumpless INTO mode 3...
    ELSE
        ...reset PID on any other transition...
    END_IF;
END_IF;
```

**After:**
```scl
IF #Control_Mode <> #Ctrl_Mode_prv THEN
    IF #Control_Mode = 3 THEN
        ...unchanged...
    ELSIF #Control_Mode = 4 THEN    // [ADDED]
        #PF_I := #Ramps_Qcmd;       // pre-load integrator → no Q jump on mode switch
    ELSE
        ...existing PID reset...
        IF #Ctrl_Mode_prv = 4 THEN  // [ADDED] also reset PF_I when leaving Mode 4
            #PF_I := 0.0;
        END_IF;
    END_IF;
END_IF;
```

**Why pre-load `PF_I := Ramps_Qcmd`:**
When switching INTO Mode 4, the current ramp accumulator (`Ramps_Qcmd`) holds the Q command the
plant is already producing. Pre-loading the integrator to this value means the first PI output is
approximately equal to the current Q command — no step change in Q output at the mode transition.

**Why reset `PF_I` when leaving Mode 4:**
If the operator switches from Mode 4 to Mode 0/1/3, the Mode 4 integrator may hold a large value.
Resetting it prevents a spurious jump if Mode 4 is re-entered later.

---

### 7. Mode 4 CASE block — inserted before ELSE (Mode 2 Off)

Control law:
```
Q_poc_required = P_poc × tan(arccos(|PF_target|)) × sign(PF_target)
Q_error        = Q_poc_required − Q_poc_measured
PF_unsat       = Kp × Q_error + PF_I
Q_command      = clamp(PF_unsat, −Q_ind_interp, +Q_cap_interp)
PF_I           = PF_I + Ki × Q_error × dt + (dt/Tt) × (Q_command − PF_unsat)
```

**Sign convention:**
- `PF_poc_target` positive = overexcited = plant injects capacitive vars = **negative Q** in the
  system's convention (positive Q = inductive = absorb). The formula multiplies by −1 first, then
  reverses for negative PF target:
  ```
  Q_poc_req = -(P_poc × tan_phi)       for positive PF_target
  Q_poc_req = +(P_poc × tan_phi)       for negative PF_target
  ```
- `Q_poc_kVAr` positive = inductive (plant absorbs) — verify sign with actual grid meter before commissioning.

**Anti-windup (back-calculation, same structure as Mode 3 PID):**
When `Q_command` hits the capability limit, `(Q_command − PF_unsat) ≠ 0`. This difference, divided
by `PF_Tt`, is added to the integrator update — it bleeds the integrator back toward the saturation
boundary. Without this, the integrator would wind up during curtailment and cause overshoot when
the limit is released.

**Why capability clamp uses interpolated table limits:**
The Mode 4 output is a Q command to the plant-level ramp and dispatcher. It must respect the ANRE
P-Q capability envelope (Stage 1 table clamp). Stage 2 (SMA physical envelope) is applied
downstream in the existing post-ramp clamp section.

**Guard `P_poc_kW > 0.0`:**
When plant is not producing (night, curtailed to zero), `tan(arccos(PF))` is undefined in terms of
real Q. The guard forces `Q_poc_req = 0` when P = 0, avoiding a division issue and unnecessary Q
injection when the plant is idle.

---

### 8. Q ramp bypass — condition extended

**Before:**
```scl
IF #Control_Mode = 3 THEN
    #Ramps_Qcmd := #Q_command;
END_IF;
```

**After:**
```scl
IF #Control_Mode = 3 OR #Control_Mode = 4 THEN   // [CHANGED]
    #Ramps_Qcmd := #Q_command;
END_IF;
```

**Why:** The Mode 4 PI integrator already rate-limits the Q command (Ki × Q_error × dt is the ramp
mechanism). Applying the external Q ramp on top would add unnecessary delay and interfere with the
PI anti-windup calculation. The `Ramps_Qcmd := Q_command` assignment keeps the ramp accumulator
tracking the PI output so that bumpless handover to modes 0/1 remains clean.

---

---

### 9. Mode 5 CASE block — Fixed Q at POC closed-loop PI

**Tag:** `[ADDED MOD_POC_Q_CL]`

**Why Mode 5 and not modifying Mode 0:**
Mode 0 (open-loop Fixed Q) remains useful when the upstream EMS/SCADA has its own outer loop and
expects the PLC to follow a Q command directly without adding another integrator. Adding a second
integrator in that case would cause instability. Mode 5 is the explicit closed-loop version — the
operator deliberately selects it when they want the PLC to close the loop at the POC.

**Control law (identical to Mode 4 except Q target source):**
```
Q_err    = Q_setpoint_ext − Q_poc_kVAr     ← target is Cmd_Q, not derived from PF
PF_unsat = Kp × Q_err + PF_I
Q_cmd    = clamp(PF_unsat, −Q_ind_interp, +Q_cap_interp)
PF_I    += Ki × Q_err × dt + (dt/Tt) × (Q_cmd − PF_unsat)   ← anti-windup
```

**Reuses from Mode 4 (no new variables or DB fields):**
- Static: `PF_I` (same integrator)
- Inputs: `PF_Kp`, `PF_Ki`, `PF_Tt`, `Q_poc_kVAr`, `P_poc_kW`
- Outputs: `Q_poc_error` (= Q_setpoint_ext − Q_poc), `Q_poc_required` (= Q_setpoint_ext), `PF_poc_actual`

**Bumpless transfer and reset:**
- Extended `ELSIF #Control_Mode = 4 OR 5` — bumpless entry pre-loads `PF_I := Ramps_Qcmd`
- Extended `IF #Ctrl_Mode_prv = 4 OR 5` — resets `PF_I` when leaving either closed-loop mode
- `PF_Reset` one-shot and FALLBACK reset apply to both modes (same `PF_I`)

**Ramp bypass:**
- Extended `IF Control_Mode = 3 OR 4 OR 5` — PI already rate-limits, external ramp bypassed

---

## Mode summary

| `VArControl_Mode` | Mode | Loop closed at | Q target |
|---|---|---|---|
| 0 | Fixed Q (open loop) | — | `Cmd_Q` directly |
| 1 | U droop | MV busbar | Voltage deviation |
| 2 | Off | — | 0 |
| 3 | U PID | MV busbar | Voltage setpoint |
| 4 | POC PF PI | POC | Derived from `PF_poc_target` and `P_poc` |
| 5 | POC Q PI | POC | `Cmd_Q` directly (closed-loop) |

---

## Activation

**Mode 4 (POC PF closed-loop):**
```
"PPC_Controller".VArControl_Mode := 4
Cmd_VArMode := 1
```

**Mode 5 (POC Q closed-loop):**
```
"PPC_Controller".VArControl_Mode := 5
Cmd_VArMode := 1
```

In both cases `Cmd_VArMode = 2` (per-inverter PF dispatch) must NOT be used simultaneously —
Modes 4 and 5 output goes through the Mode 1 Q dispatch path.

---

## Tuning (applies to both Mode 4 and Mode 5)

1. Start: `PF_Kp = 0.0`, `PF_Ki = 50.0`, `PF_Tt = 5.0`
2. Monitor `Q_poc_error` and `PF_poc_actual` on HMI
3. If too slow: double `PF_Ki`; if oscillating: halve `PF_Ki` or increase `PF_Tt`
4. Add small `PF_Kp` (10–50) only after Ki is stable for faster initial response
