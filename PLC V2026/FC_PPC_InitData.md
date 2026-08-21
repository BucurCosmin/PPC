# FC_PPC_InitData — Change Log

## Overview

This FC writes safe default values to `"PPC_Controller"` DB (DB39) and resets runtime state in
the FB instance DBs. It is called:

- **OB100 (Startup OB):** unconditionally on every CPU power-on or code download
- **OB30 (cyclic):** guarded by `"PPC_Controller".ResetToDefaults`, then self-cleared

---

## Why the change is needed

The new Mode 4 (POC PF PI control) introduces five new fields in `"PPC_Controller"` DB and one new
static variable (`PF_I`) in `FB_PPC_Controller_DB.QCap_IDB`. Without initialisation:

- On first download, all new REAL fields default to `0.0` — `PF_Ki = 0` means the integrator does
  nothing, which is safe but non-functional.
- `PF_poc_target = 0.0` would target zero PF (full reactive), causing the plant to demand maximum Q
  if Mode 4 is activated accidentally.
- `PF_Tt = 0.0` disables anti-windup, risking integrator windup during commissioning.

The defaults written here ensure Mode 4 is safe to activate without pre-configuration.

---

## Change Applied

**Tag:** `[ADDED MOD_POC_PF]`

Added after the existing `Q_Ramp_Fast_Sel` line in the reactive power section:

```scl
// [ADDED MOD_POC_PF] Mode 4 POC PF closed-loop PI defaults
"PPC_Controller".PF_poc_target := 1.0;    // unity PF - safe initial default
"PPC_Controller".PF_Kp         := 0.0;    // pure integrator to start
"PPC_Controller".PF_Ki         := 50.0;   // kVAr/(kVAr.s) - tune slowly on site
"PPC_Controller".PF_Tt         := 5.0;    // s, anti-windup time constant
// Reset PF integrator on startup / defaults reset
"FB_PPC_Controller_DB".QCap_IDB.PF_I := 0.0;
```

---

## Default Value Rationale

| Field | Default | Reason |
|---|---|---|
| `PF_poc_target` | `1.0` | Unity PF is safe — no reactive demand when Mode 4 first enabled |
| `PF_Kp` | `0.0` | Pure integrator start — eliminates P-gain kick on first activation |
| `PF_Ki` | `50.0` | Conservative starting gain. Gives ~2 s response for 100 kVAr error at 100 ms scan rate. Tune up on site if too slow |
| `PF_Tt` | `5.0` | Anti-windup time constant 5 s — prevents integrator runaway during capability saturation |
| `PF_I` | `0.0` | Clean integrator state on startup/reset — avoids spurious Q jump |

---

## What is NOT written here

- `VArControl_Mode` — not changed by this addition. Remains `0` (fixed Q) by default.
  Mode 4 must be deliberately activated by SCADA writing `VArControl_Mode = 4`.
- `PF_Reset` — not written. It is a SCADA one-shot flag; setting it here would trigger a reset
  on every defaults-reset call, which is already covered by `PF_I := 0.0` above.

---

## Prerequisite

Before `FC_PPC_InitData` can reference `PF_poc_target`, `PF_Kp`, `PF_Ki`, `PF_Tt`, and `PF_I`,
these fields must exist in `"PPC_Controller"` DB (DB39) and in
`"FB_PPC_Controller_DB".QCap_IDB`. Add them in TIA Portal before downloading this code:

**DB39 fields to add (REAL, default 0.0 except as noted):**
- `PF_poc_target` (REAL, default 1.0)
- `PF_Kp` (REAL, default 0.0)
- `PF_Ki` (REAL, default 50.0)
- `PF_Tt` (REAL, default 5.0)
- `PF_Reset` (BOOL, default FALSE)
- `Q_poc_required` (REAL) — diagnostic, read-only from SCADA
- `Q_poc_error` (REAL) — diagnostic
- `PF_poc_actual` (REAL) — diagnostic

`PF_I` is a static variable inside `FB_PPC_QCapability` — it appears automatically in
`FB_PPC_Controller_DB.QCap_IDB` once `FB_PPC_QCapability.scl` is compiled with the new VAR block.
No manual DB editing required for `PF_I`.
