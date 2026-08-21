# FC_PPC_ReactiveControl — Change Log

## Overview

This FC distributes the plant-level reactive power command across all online inverters.
It operates in three modes selected by `Plant_VArMode` (= `Cmd_VArMode` from FB_PPC_Controller):

| Mode | Behaviour |
|---|---|
| 0 | Off — write `VArMode = 303` (Off) to all inverters |
| 1 | Q control — distribute `Q_cmd_kVAr` proportionally by `VArAval` |
| 2 | **Modified** — PF→Q dispatch (see below) |

---

## Change: Mode 2 — PF → Q dispatch rewrite

**Tag:** `[CHANGED MOD_PF_Dispatch]`

### What was there before

Mode 2 had two branches controlled by `Sim_Mode`:

- **Sim_Mode = FALSE (real mode):** Wrote `PFSpt` (power factor setpoint register, FIX4 ×10000)
  and set `VArMode = 1075` (PFCtlCom — inverter controls Q autonomously from PF target).
- **Sim_Mode = TRUE (simulation):** Computed Q = P × tan(arccos(|PF|)) from `WSpt` (commanded P),
  clamped to SMA envelope, wrote as `VArSpt + VArCtlCom (1072)`.

### Problem

`VArMode = 1075` (PFCtlCom) causes the SMA SC 4600 UP inverter to go into error/fault on this
installation. The inverter rejects the command and latches a fault, requiring manual reset.

A second issue: the simulation branch used `WSpt` (commanded P) instead of `Wactive` (measured P).
When the inverter is ramping or curtailed, `WSpt ≠ Wactive`, causing the PF→Q conversion to
produce a Q setpoint that doesn't match actual plant output — the reactive output overshoots or
undershoots the PF target.

### Fix

**Both branches removed.** Mode 2 now always:

1. Computes `Q = Wactive × tan(arccos(|PF|))` where `Wactive` is the actual measured active power
   read from the inverter Modbus register (not the commanded setpoint).
2. Applies sign from `Targets_PF` (negative = lagging/inductive = absorb vars).
3. Calls `FC_SMA_QEnvelope` to clamp Q to the physical apparent power limit at current P and U.
4. Writes result as `VArSpt` + `VArMode = 1072` (VArCtlCom — PLC controls Q directly).

**Why `Wactive` and not `WSpt`:**
The Q command must track actual production. If the inverter is ramping up (WSpt > Wactive) and we
use WSpt, we demand more reactive power than the inverter can provide at its current active output,
violating the P-Q envelope. Using `Wactive` keeps Q within the SMA physical capability at all times.

**Why VArCtlCom (1072) and not PFCtlCom (1075):**
PFCtlCom delegates PF regulation to the inverter's internal controller. On this hardware it
triggers a fault. VArCtlCom sends an explicit Q setpoint that the inverter follows without
autonomous regulation — stable and fault-free.

### Side effects

- `Sim_Mode` input remains declared in VAR_INPUT (removing it would break the FB interface).
  TIA Portal may show an "unused input" warning — harmless.
- `PFSpt` is always written as 0 in Mode 2 (previously held the FIX4 PF value in real mode).
  The inverter ignores PFSpt when VArMode = VArCtlCom.

### Changed lines (marked `[CHANGED]` in code)

| Location | Old value | New value | Reason |
|---|---|---|---|
| Mode 2 case label | `PF setpoint` | `PF->Q dispatch` | Reflects new algorithm |
| Q calculation source | `WSpt` | `Wactive` | Track actual P, not commanded P |
| FC_SMA_QEnvelope P_kW | `WSpt` | `Wactive` | Consistent with Q calculation |
| `VArMode` | `1075` (PFCtlCom) | `1072` (VArCtlCom) | PFCtlCom causes inverter fault |
| IF/ELSE Sim_Mode block | Present | Removed | Single code path, no mode branching |
