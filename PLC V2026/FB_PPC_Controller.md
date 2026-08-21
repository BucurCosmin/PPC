# FB_PPC_Controller — Change Log

## Overview

This FB is the main PPC orchestrator. It calls eight FCs/FBs in fixed order each OB30 scan (100 ms).
The changes here are plumbing only — no control logic resides in this FB. All Mode 4 logic is in
`FB_PPC_QCapability`. This FB's role is to:

1. Accept POC measurements as inputs (from OB30 wiring)
2. Pass them through to the `QCap_IDB` call
3. Mirror the Mode 4 diagnostic outputs to `"PPC_Controller"` DB for SCADA/HMI visibility
4. Clear the `PF_Reset` one-shot flag after `QCap_IDB` has processed it

---

## Why the changes are needed

`FB_PPC_QCapability` needs `P_poc_kW` and `Q_poc_kVAr` (POC grid meter measurements) as inputs to
compute the Q error for the POC PF PI controller (Mode 4). These measurements are read from the
grid meter DB in OB30 and must be passed through FB_PPC_Controller → QCap_IDB.

The Mode 4 diagnostic outputs (`Q_poc_required`, `Q_poc_error`, `PF_poc_actual`) live in the
QCap_IDB instance. They need to be mirrored to `"PPC_Controller"` DB (DB39) so SCADA and HMI can
read them — the same pattern used for Mode 3 PID diagnostics (`PID_I_term`, `U_error_kV`, etc.)

---

## Changes Applied

All changes are tagged `[ADDED MOD_POC_PF]` in the code.

---

### 1. VAR_INPUT — 2 new inputs added after `Sim_Mode`

| Input | Type | Source (OB30 wiring) | Purpose |
|---|---|---|---|
| `P_poc_kW` | REAL | `"GridMeter".P_kW` | Active power at POC from grid meter (kW) |
| `Q_poc_kVAr` | REAL | `"GridMeter".Q_kVAr` | Reactive power at POC from grid meter (kVAr) |

**Sign convention for `Q_poc_kVAr` (VERIFY with actual meter before commissioning):**
- Positive = plant absorbing reactive power (inductive/underexcited)
- Negative = plant injecting reactive power (capacitive/overexcited)

If the grid meter reports with the opposite sign convention, negate at the OB30 wiring point:
```scl
Q_poc_kVAr := -"GridMeter".Q_kVAr,   // negate if meter sign is reversed
```

---

### 2. QCap_IDB call — 7 new parameters added, comma added to PID_Reset

**Before (PID_Reset was last parameter, no comma):**
```scl
#QCap_IDB(
    ...
    PID_Reset        := "PPC_Controller".PID_Reset
);
```

**After:**
```scl
#QCap_IDB(
    ...
    PID_Reset        := "PPC_Controller".PID_Reset,   // comma added — no longer last
    P_poc_kW      := #P_poc_kW,           // [ADDED MOD_POC_PF]
    Q_poc_kVAr    := #Q_poc_kVAr,         // [ADDED MOD_POC_PF]
    PF_poc_target := "PPC_Controller".PF_poc_target,   // [ADDED MOD_POC_PF]
    PF_Kp         := "PPC_Controller".PF_Kp,           // [ADDED MOD_POC_PF]
    PF_Ki         := "PPC_Controller".PF_Ki,           // [ADDED MOD_POC_PF]
    PF_Tt         := "PPC_Controller".PF_Tt,           // [ADDED MOD_POC_PF]
    PF_Reset      := "PPC_Controller".PF_Reset         // [ADDED MOD_POC_PF]
);
```

**Why from `"PPC_Controller"` DB and not direct inputs:**
PF tuning parameters (`PF_Kp`, `PF_Ki`, `PF_Tt`, `PF_poc_target`) are SCADA-writable at runtime.
Routing them through the global DB means SCADA can change them without recompiling OB30 or the FB.
The same pattern is used for all other tuning parameters (U_Kp, U_Ki, U_Droop_pct, etc.).

---

### 3. Diagnostic mirror — 4 lines added after `PID_Reset := FALSE`

```scl
// [ADDED MOD_POC_PF] Mode 4 POC PF diagnostics
"PPC_Controller".Q_poc_required := #QCap_IDB.Q_poc_required;
"PPC_Controller".Q_poc_error    := #QCap_IDB.Q_poc_error;
"PPC_Controller".PF_poc_actual  := #QCap_IDB.PF_poc_actual;
"PPC_Controller".PF_Reset       := FALSE;   // clear one-shot after FB processed it
```

**Why mirror here and not read directly from QCap_IDB:**
SCADA and HMI read from `"PPC_Controller"` DB (DB39) — the single source of truth for all PPC
diagnostics. Direct reads from `"FB_PPC_Controller_DB".QCap_IDB.*` would require SCADA to know
the internal IDB structure, which is an implementation detail that can change. The mirror pattern
(used for all QCap and FreqResp diagnostics) keeps the SCADA/HMI interface stable.

**Why `PF_Reset := FALSE` here:**
`PF_Reset` is a one-shot flag written by SCADA. The FB_PPC_QCapability reads it each scan and
resets `PF_I` when TRUE. Clearing it here (after QCap has run) ensures exactly one reset scan:
SCADA writes TRUE → one OB30 cycle → QB_IDB sees TRUE, resets PF_I → this line clears it → done.
The same pattern is used for `PID_Reset` (existing, line above).

---

## OB30 Wiring (required — TIA Portal only, not SCL)

At the FB_PPC_Controller call in OB30, wire the two new inputs:

```scl
"FB_PPC_Controller_Instance"(
    ...existing inputs...,
    P_poc_kW   := "GridMeter".P_kW,       // ← from grid meter DB
    Q_poc_kVAr := "GridMeter".Q_kVAr,     // ← from grid meter DB (verify sign!)
    ...
);
```

Replace `"GridMeter"` and field names with the actual DB tag names used for the POC grid meter in
this project. Check DB39 `"PPC_Controller"` for the existing grid meter DB name — it is likely
already reading `P_actual_kW` from the same meter.
