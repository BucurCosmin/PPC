# PPC Controller Design — S7-1500 SCL

## Overview

Plant Power Controller (PPC) for SMA inverter plant running on Siemens S7-1500.
Implementation language: SCL. Structure: one main **FB** calling multiple **FCs** for maintainability.

---

## Data Structures (from TIA Portal exports)

### UDT: `Inverter_controller`

| Field | Type | Description |
|---|---|---|
| Enabled | Bool | Inverter enabled flag |
| RemReady | Bool | Remote-ready status |
| Error | Bool | Inverter fault |
| CommError | Bool | Communication fault |
| OperMode | DInt | InvOpMod setpoint → to inverter (308=Operation, 303=Stop) |
| Wactive | DInt | Active power actual (feedback, from InvMs.TotW input reg 28) |
| Qactive | DInt | Reactive power actual (feedback) |
| WMode | DInt | Active power control mode selection |
| VArMode | DInt | Reactive power control mode selection |
| WSpt | DInt | Active power setpoint → to inverter |
| VArSpt | DInt | Reactive power setpoint → to inverter |
| PFSpt | DInt | Power factor setpoint → to inverter |
| WAval | DInt | Available active power (from inverter) |
| VArAval | DInt | Available reactive power (from inverter) |
| PwrOffReas | DInt | Power-off reason code |
| DrtStt | DInt | Derating state |

### DB39: `PPC_Controller`

**Inverter references:**
- `PPC_Inverters`: `Array[0..9] of Inverter_controller` — used internally by PPC logic; passed as VAR_IN_OUT to each FC
- `Inverter1..Inverter10`: Individual named instances — same physical inverters as above, used for HMI/SCADA visibility only (read-only mirror, not written by PPC FCs)

**Plant-level signals:**

| Field | Type | Unit | Description |
|---|---|---|---|
| START_CONTROLLER | Bool | — | Enable PPC logic |
| WRtg_kW | Real | kW | Rated active power per inverter (from register 184); used to convert WAval from pu to kW |
| P_RampUp | Real | kW/s | Active power ramp-up rate |
| P_RampDown | Real | kW/s | Active power ramp-down rate |
| Q_Ramp | Real | kVAr/s | Reactive power ramp rate |
| PF_Ramp | Real | /s | Power factor ramp rate |
| Plant_P_meas | Real | kW | Measured plant active power (PCC) |
| Plant_Q_meas | Real | kVAr | Measured plant reactive power (PCC) |
| Plant_N_Online | Int | — | Number of inverters currently online |
| Plant_Mode | Int | — | 0=LOCAL / 1=REMOTE_IEC / 2=FALLBACK (set by ModeManager) |
| Plant_VArMode | Int | — | 0=Off / 1=Q / 2=PF (written from FB input Cmd_VArMode) |
| AnyFault | Bool | — | TRUE if any inverter fault active (set by FaultHandler) |
| Targets_P | Real | kW | Active power target — written by FB from its IN parameter each cycle |
| Targets_Q | Real | kVAr | Reactive power target — written by FB from its IN parameter each cycle |
| Targets_PF | Real | — | Power factor target — written by FB from its IN parameter each cycle |
| Limits_PmaxPlant | Real | kW | Sum of online WAval in kW (computed by InverterMonitor) |
| Limits_QmaxPlant | Real | kVAr | Sum of online VArAval in kVAr (computed by InverterMonitor) |
| Ramps_Pcmd | Real | kW | Ramped P command (internal, output of RampControl) |

---

## Architecture

```
FB_PPC_Controller  (main FB, called every PLC cycle)
│
├── FC_PPC_InverterMonitor      ① Scan inverters, count online, sum WAval
├── FC_PPC_ModeManager          ② Determine Plant_Mode (LOCAL / REMOTE / FALLBACK)
├── FC_PPC_RampControl          ③ Apply ramp rates → produce Ramps_Pcmd
├── FC_PPC_PowerDistribution    ④ Distribute P setpoint equally among online inverters
├── FC_PPC_ReactiveControl      ⑤ Distribute Q or PF setpoint
└── FC_PPC_FaultHandler         ⑥ Handle CommError / inverter errors / watchdog
```

Call order matters — each FC feeds results to the next.

---

## Operating Modes

| Mode value | Name | Description |
|---|---|---|
| 0 | LOCAL | Targets come from HMI/local DB; no remote command needed |
| 1 | REMOTE_IEC | Targets received via IEC 61850 / Modbus TCP from grid operator |
| 2 | FALLBACK | Communication lost → revert to safe fallback power level |

Mode transitions:
- LOCAL → REMOTE_IEC: when communication link is healthy and `START_CONTROLLER = TRUE`
- REMOTE_IEC → FALLBACK: when IEC watchdog times out (e.g. no telegram for >30 s)
- FALLBACK → REMOTE_IEC: when communication is restored and watchdog is reset

---

## FC Specifications

---

### FC_PPC_InverterMonitor

**Purpose:** Iterate over all 10 inverters, aggregate status and available power.

**Inputs (via PPC_Controller DB):** `PPC_Inverters[0..9]`

**Outputs written to DB:**
- `Plant_N_Online` — count of inverters where `Enabled=TRUE AND RemReady=TRUE AND NOT Error AND NOT CommError`
- `Limits_PmaxPlant` — sum of `WAval` for all online inverters (in kW, scaled if needed)

**WAval/VArAval scaling:** Both are pu × 10000 (FIX4). To convert to engineering units:
- `kW   = DINT_TO_REAL(WAval)  / 10000.0 × WRtg_kW`
- `kVAr = DINT_TO_REAL(VArAval)/ 10000.0 × WRtg_kW`  *(VArRtg approximated = WRtg for same-model inverters)*

**For proportional distribution** the WRtg factor cancels when computing shares (WAval_i / ΣWAval_j), so raw DInt values can be used directly for ratio math — WRtg is only needed for the absolute kW limit (Limits_PmaxPlant).

**Logic sketch:**
```scl
Plant_N_Online   := 0;
Limits_PmaxPlant := 0.0;
Limits_QmaxPlant := 0.0;

FOR i := 0 TO 9 DO
    IF PPC_Inverters[i].Enabled
       AND PPC_Inverters[i].RemReady
       AND NOT PPC_Inverters[i].Error
       AND NOT PPC_Inverters[i].CommError
    THEN
        Plant_N_Online   := Plant_N_Online + 1;
        // Convert pu×10000 → kW/kVAr using rated power
        Limits_PmaxPlant := Limits_PmaxPlant
            + (DINT_TO_REAL(PPC_Inverters[i].WAval)   / 10000.0 * WRtg_kW);
        Limits_QmaxPlant := Limits_QmaxPlant
            + (DINT_TO_REAL(PPC_Inverters[i].VArAval) / 10000.0 * WRtg_kW);
    END_IF;
END_FOR;
```

---

### FC_PPC_ModeManager

**Purpose:** Evaluate communication watchdog and set `Plant_Mode`.

**Inputs:**
- IEC/Modbus watchdog heartbeat bit (external input to FB, toggling on each received telegram)
- `START_CONTROLLER`
- Configurable watchdog timeout (static var in FB, default T#30S)

**Logic:**
1. If `START_CONTROLLER = FALSE` → hold outputs, no mode change
2. If watchdog heartbeat toggles within timeout → `Plant_Mode := 1` (REMOTE_IEC)
3. If watchdog timeout expires (no toggle for >30 s) → `Plant_Mode := 2` (FALLBACK)
4. If HMI forces LOCAL override → `Plant_Mode := 0`

**Watchdog implementation:**
- Detect rising edge of `IEC_Watchdog` bit to confirm new telegram received
- `TON` timer: reset (`IN := FALSE` pulse) on each edge; if `Q = TRUE` → FALLBACK
- Called every OB30 tick (100 ms); timer runs in FB static memory

---

### FC_PPC_RampControl

**Purpose:** Limit the rate of change of the P command to protect inverters and grid.

**Inputs:** `Targets_P`, `P_RampUp`, `P_RampDown`, cycle time `dt`

**Output:** `Ramps_Pcmd`

**Logic:**
```scl
delta := Targets_P - Ramps_Pcmd;

IF delta > 0.0 THEN
    // Ramping up
    Ramps_Pcmd := Ramps_Pcmd + MIN(delta, P_RampUp * dt);
ELSIF delta < 0.0 THEN
    // Ramping down
    Ramps_Pcmd := Ramps_Pcmd - MIN(ABS(delta), P_RampDown * dt);
END_IF;

// Apply absolute limit
Ramps_Pcmd := MIN(Ramps_Pcmd, Limits_PmaxPlant);
Ramps_Pcmd := MAX(Ramps_Pcmd, 0.0);
```

**Note:** `dt` = OB30 cycle time in seconds. FB is called from OB30 (default 100 ms → `CycleTime_s = 0.1`). Pass as IN parameter to FC.

---

### FC_PPC_PowerDistribution

**Purpose:** Split `Ramps_Pcmd` equally among all online inverters and write `WSpt`.

**WSpt unit:** kW, direct integer value (scaling = 1).

**WMode (GriMng.WMod) ENUM:**

| Value | Name | Description |
|---|---|---|
| 303 | Off | No active power control |
| 1079 | WCtlCom | Remote W setpoint via Modbus |

**Strategy — Proportional distribution by WAval:**

Each online inverter receives a share of `Ramps_Pcmd` proportional to its available active power (WAval). Since WAval pu values have the same WRtg denominator for same-model inverters, raw DInt values can be used directly for the ratio.

```scl
// sumWAval_raw = sum of raw WAval DInt for all online inverters (computed inline)
sumWAval_raw := 0;
FOR i := 0 TO 9 DO
    IF inverter_is_online(i) THEN
        sumWAval_raw := sumWAval_raw + PPC_Inverters[i].WAval;
    END_IF;
END_FOR;

FOR i := 0 TO 9 DO
    IF inverter_is_online(i) AND sumWAval_raw > 0 THEN
        // share = WAval_i / ΣWAval_j  (dimensionless; WRtg cancels)
        share := DINT_TO_REAL(PPC_Inverters[i].WAval) / DINT_TO_REAL(sumWAval_raw);
        PPC_Inverters[i].WSpt  := REAL_TO_DINT(Ramps_Pcmd * share);
        PPC_Inverters[i].WMode := 1079;  // WCtlCom
    ELSE
        PPC_Inverters[i].WSpt  := 0;
        PPC_Inverters[i].WMode := 303;   // Off
    END_IF;
END_FOR;
```

**Limit check:** `Ramps_Pcmd` is already clamped to `Limits_PmaxPlant` by RampControl, so no individual inverter will receive more than its WAval in kW.

---

### FC_PPC_ReactiveControl

**Purpose:** Distribute reactive power or power factor setpoint.

**VArMode (GriMng.VArMod) ENUM — confirmed values:**

| Value | Name | Description |
|---|---|---|
| 303 | Off | No reactive control (Q = 0) |
| 1072 | VArCtlCom | Remote Q setpoint via Modbus (write VArSpt in kVAr) |
| 1075 | PFCtlCom | Remote PF setpoint via Modbus (write PFSpt, scaled ×10000) |

**VArSpt unit:** kVAr, direct integer value (scaling = 1).  
**PFSpt scaling:** ×10000 (e.g. PF 0.950 → write 9500; PF 1.000 → write 10000).

**Plant_VArMode values (plant-level selector, stored in DB39):**

| Plant_VArMode | Inverter mode | Description |
|---|---|---|
| 0 | Off (303) | No reactive control |
| 1 | VArCtlCom (1072) | Fixed Q setpoint |
| 2 | PFCtlCom (1075) | Fixed PF setpoint |

**Q distribution strategy:** Proportional to VArAval (same ratio approach as WAval for P). PF mode: same setpoint to all online inverters (PF is a ratio, uniform target is correct — Q distributes naturally proportional to P output).

**Logic:**
```scl
// Pre-compute sumVArAval_raw for Q mode
sumVArAval_raw := 0;
FOR i := 0 TO 9 DO
    IF inverter_is_online(i) THEN
        sumVArAval_raw := sumVArAval_raw + PPC_Inverters[i].VArAval;
    END_IF;
END_FOR;

FOR i := 0 TO 9 DO
    IF inverter_is_online(i) THEN
        CASE Plant_VArMode OF
            0: // No Q control
               PPC_Inverters[i].VArSpt  := 0;
               PPC_Inverters[i].VArMode := 303;   // Off

            1: // Q proportional to VArAval
               IF sumVArAval_raw > 0 THEN
                   share := DINT_TO_REAL(PPC_Inverters[i].VArAval)
                            / DINT_TO_REAL(sumVArAval_raw);
                   PPC_Inverters[i].VArSpt := REAL_TO_DINT(Targets_Q * share);
               ELSE
                   PPC_Inverters[i].VArSpt := 0;
               END_IF;
               PPC_Inverters[i].VArMode := 1072;  // VArCtlCom

            2: // PF uniform — same target for all online inverters
               PPC_Inverters[i].PFSpt   := REAL_TO_DINT(Targets_PF * 10000.0);
               PPC_Inverters[i].VArMode := 1075;  // PFCtlCom
        END_CASE;
    ELSE
        PPC_Inverters[i].VArSpt  := 0;
        PPC_Inverters[i].PFSpt   := 0;
        PPC_Inverters[i].VArMode := 303;
    END_IF;
END_FOR;
```

---

### FC_PPC_FaultHandler

**Purpose:** Handle inverter-level and plant-level faults. Safe-state logic.

**OperMode (InvOpMod) ENUM — confirmed values:**

| Value | Name | Description |
|---|---|---|
| 308 | Operation | Normal operation (inverter running) |
| 303 | Stop | Inverter stopped / safe state |

**Triggers:**
- `CommError` on any inverter → mark offline, `WSpt := 0`, `OperMode := 303`
- `Error` on any inverter → same as CommError safe state
- All inverters offline → `Ramps_Pcmd := 0`, clamp ramp output

**FALLBACK mode behaviour:**
- Confirmed: Fallback P = 0 (full stop via `OperMode := 303`)
- Reason: writing `WSpt := 0` alone can trigger PwrOffReas "Low Power SetPoint"; `InvOpMod=303` issues a clean Stop command
- Recovery: when mode returns to REMOTE_IEC, write `RemRdy=308` then `OperMode := 308` before resuming WSpt

**Safe state per inverter:**
```scl
// Applied to faulted or FALLBACK inverters
PPC_Inverters[i].OperMode := 303;  // Stop (InvOpMod)
PPC_Inverters[i].WSpt     := 0;
PPC_Inverters[i].VArSpt   := 0;
PPC_Inverters[i].PFSpt    := 0;
```

- Do NOT write to healthy inverters in partial-fault scenarios — they continue operating

---

## Main FB: `FB_PPC_Controller`

### Interface

**Inverter array approach (decided):**  
`PPC_Inverters[0..9]` is passed as `VAR_IN_OUT` to each FC. This keeps the FC signatures clean and avoids 10 individual IN_OUT parameters. `Inverter1..Inverter10` in DB39 are used for HMI/SCADA read visibility only — the PPC FCs write exclusively to the array.

**INPUT:**
| Variable | Type | Description |
|---|---|---|
| EN_PPC | Bool | Enable PPC |
| IEC_Watchdog | Bool | Toggling heartbeat from upstream comms thread (edge = new telegram) |
| CycleTime_s | Real | OB30 cycle time in seconds (default 0.1 for 100 ms) |
| Cmd_P | Real | Active power target from upstream (kW) |
| Cmd_Q | Real | Reactive power target from upstream (kVAr) |
| Cmd_PF | Real | Power factor target from upstream (e.g. 0.95) |
| Cmd_VArMode | Int | Reactive control mode from upstream (0=Off / 1=Q / 2=PF) |
| LocalMode_Req | Bool | HMI LOCAL override request (TRUE = force LOCAL mode) |

**OUTPUT:**
| Variable | Type | Description |
|---|---|---|
| PPC_Active | Bool | TRUE when Plant_Mode = 1 (REMOTE_IEC) |
| PPC_Fault | Bool | Any PPC-level fault active |
| Mode_Out | Int | Current Plant_Mode (0/1/2) |

**STATIC (retained in FB instance):**
| Variable | Type | Description |
|---|---|---|
| Watchdog_TON | TON | Watchdog timer instance |
| Watchdog_LastBit | Bool | Previous IEC_Watchdog state for rising-edge detection |
| Watchdog_Timeout | Time | Configurable timeout, default T#30S |

### Call sequence in FB body:

```scl
// Guard
IF NOT EN_PPC THEN
    // Safe state: all inverters stop via FaultHandler, then return
    FC_PPC_FaultHandler(DB := PPC_Controller, ForceStop := TRUE);
    PPC_Active := FALSE;
    RETURN;
END_IF;

// Copy FB inputs → DB working fields (FCs read from DB)
PPC_Controller.Targets_P      := Cmd_P;
PPC_Controller.Targets_Q      := Cmd_Q;
PPC_Controller.Targets_PF     := Cmd_PF;
PPC_Controller.Plant_VArMode  := Cmd_VArMode;

// ① Scan inverters — updates Plant_N_Online, Limits_PmaxPlant, Limits_QmaxPlant
FC_PPC_InverterMonitor(DB := PPC_Controller);

// ② Determine Plant_Mode from watchdog + LocalMode_Req
FC_PPC_ModeManager(
    Watchdog_Bit   := IEC_Watchdog,
    LocalMode_Req  := LocalMode_Req,
    WD_TON         := Watchdog_TON,
    WD_Timeout     := Watchdog_Timeout,
    DB             := PPC_Controller
);

// ③ Ramp Targets_P → Ramps_Pcmd (clamped to Limits_PmaxPlant)
FC_PPC_RampControl(
    dt := CycleTime_s,
    DB := PPC_Controller
);

// ④ Distribute Ramps_Pcmd proportionally by WAval → write WSpt, WMode
FC_PPC_PowerDistribution(DB := PPC_Controller);

// ⑤ Distribute Q or PF proportionally by VArAval → write VArSpt/PFSpt, VArMode
FC_PPC_ReactiveControl(DB := PPC_Controller);

// ⑥ Override faulted/CommError inverters to safe state; apply FALLBACK logic
FC_PPC_FaultHandler(DB := PPC_Controller, ForceStop := FALSE);

// Write outputs
Mode_Out   := PPC_Controller.Plant_Mode;
PPC_Active := (PPC_Controller.Plant_Mode = 1);
PPC_Fault  := PPC_Controller.AnyFault;  // Bool set by FaultHandler
```

---

## Scaling Conventions

Confirmed from SMA Modbus TCP/IP interface manual (unit ID 3):

| Signal | UDT type | DB unit | Scale factor | Register unit | Notes |
|---|---|---|---|---|---|
| WAval | DInt | pu×10000 | ÷10000 × WRtg_kW | per-unit S32 | Convert to kW for distribution math |
| VArAval | DInt | pu×10000 | ÷10000 × QRtg_kVAr | per-unit S32 | Same pattern as WAval |
| Wactive | DInt | pu×10000 | ÷10000 × WRtg_kW | per-unit S32 | Measured output |
| Qactive | DInt | pu×10000 | ÷10000 × QRtg_kVAr | per-unit S32 | Measured reactive output |
| WSpt | DInt | kW | × 1 | kW direct | Write integer kW value |
| VArSpt | DInt | kVAr | × 1 | kVAr direct | Write integer kVAr value |
| PFSpt | DInt | PF×10000 | ÷10000 | dimensionless ×10000 | 0.950 → write 9500 |

**WRtg_kW** (register 184, kW): rated active power per inverter. Read once at startup and store in `PPC_Controller.WRtg_kW`. Assumed uniform across all inverters in the plant. If inverters have different ratings, move WRtg into the `Inverter_controller` UDT.

**ENUM reference summary (confirmed from Modbus map):**

| Register | ENUM value | Name | Meaning |
|---|---|---|---|
| InvOpMod (Holding 0) | 308 | Operation | Inverter running — write to start |
| InvOpMod (Holding 0) | 303 | Stop/Off | Safe-state stop |
| RemRdy (Holding 2) | 308 | Ready | Put inverter in remote-ready state |
| RemRdy (Holding 2) | 303 | Standby | Remove remote-ready |
| GriMng.WMod (Holding 6) | 303 | Off | No active power control |
| GriMng.WMod (Holding 6) | 1079 | WCtlCom | Remote W setpoint via Modbus |
| GriMng.VArMod (Holding 4) | 303 | Off | No reactive power control |
| GriMng.VArMod (Holding 4) | 1072 | VArCtlCom | Remote Q setpoint via Modbus |
| GriMng.VArMod (Holding 4) | 1075 | PFCtlCom | Remote PF setpoint via Modbus |

**Start/Stop interlock sequence (mandatory):**
- To **start**: write `RemRdy=308` first, then `InvOpMod=308`
- To **stop**: write `InvOpMod=303` (optionally also `RemRdy=303`)
- `WMod=1079` must be written **before** `WSpt` (mode first, then setpoint)
- `VArMod=1072` or `1075` must be written **before** `VArSpt`/`PFSpt`

**Comms layer separation:**  
PPC FCs write only to UDT fields (e.g. `OperMode`, `WMode`, `WSpt`). A dedicated Modbus comms block (outside the PPC FB) maps UDT fields → actual holding register writes (FC16) and input register reads (FC04). The PPC control logic has no awareness of register addresses.

**WSpt/VArSpt/PFSpt readback:** Input registers 108/112/114 are the inverter's echo of the currently active setpoint (read-only). The actual write addresses are in holding registers handled by the comms block.

---

## File Structure (TIA Portal project)

```
PLC_1 [S7-1500]
├── Program blocks
│   ├── FB_PPC_Controller      [FB, SCL]  — main controller
│   ├── FC_PPC_InverterMonitor [FC, SCL]  — ①
│   ├── FC_PPC_ModeManager     [FC, SCL]  — ②
│   ├── FC_PPC_RampControl     [FC, SCL]  — ③
│   ├── FC_PPC_PowerDistribution[FC, SCL] — ④
│   ├── FC_PPC_ReactiveControl [FC, SCL]  — ⑤
│   └── FC_PPC_FaultHandler    [FC, SCL]  — ⑥
├── PLC data types
│   └── Inverter_controller    [UDT]
└── Data blocks
    └── PPC_Controller         [DB39]
```

---

## Open Questions / To Confirm

| # | Question | Status |
|---|---|---|
| 1 | SMA scaling — WAval/WSpt units | **RESOLVED** — WAval/VArAval = pu×10000 (FIX4); WSpt = kW direct (FIX0); VArSpt = kVAr direct (FIX0); PFSpt = PF×10000 (FIX4) |
| 2 | OperMode (InvOpMod) ENUM values | **RESOLVED** — 308 = Operation, 303 = Stop; RemRdy: 308 = Ready, 303 = Standby |
| 3 | WMode (GriMng.WMod) values | **RESOLVED** — 303 = Off, 1079 = WCtlCom |
| 4 | VArMode (GriMng.VArMod) values | **RESOLVED** — 303 = Off, 1072 = VArCtlCom, 1075 = PFCtlCom |
| 5 | SCADA/IEC interface — targets and mode source | **RESOLVED** — Targets_P/Q/PF and VArMode are FB input parameters (Cmd_P, Cmd_Q, Cmd_PF, Cmd_VArMode); upstream comms thread writes them to the FB call in OB30 |
| 6 | Distribution algorithm | **RESOLVED** — proportional to WAval (P) and VArAval (Q); PF mode uniform (same setpoint to all online inverters) |
| 7 | Fallback P level | **RESOLVED** — Fallback = 0 via InvOpMod=303 (Stop) |
| 8 | OB cycle time | **RESOLVED** — OB30, default 100 ms; CycleTime_s = 0.1 |
| 9 | Array vs named inverters | **RESOLVED** — same physical inverters; PPC FCs write to array only; Inverter1..10 are HMI mirrors |
| 10 | WRtg_kW availability | **RESOLVED** — all inverters same model; WRtg_kW is a plant constant in DB39 |

---

## Implementation Order

| Step | Block | Status | Notes |
|---|---|---|---|
| 1 | UDT `Inverter_controller` | Done (imported) | |
| 2 | DB39 `PPC_Controller` | Done (imported) | **Add `WRtg_kW: Real` field** |
| 3 | `FC_PPC_InverterMonitor` | To do | Uses WAval pu→kW conversion |
| 4 | `FC_PPC_ModeManager` | To do | TON watchdog, OB30 tick |
| 5 | `FC_PPC_RampControl` | To do | dt = 0.1 s |
| 6 | `FC_PPC_PowerDistribution` | To do | WSpt in kW, WMode=1079 |
| 7 | `FC_PPC_ReactiveControl` | To do | VArSpt kVAr direct, PFSpt ×10000 |
| 8 | `FC_PPC_FaultHandler` | To do | OperMode=381 for stop |
| 9 | `FB_PPC_Controller` | To do | Array VAR_IN_OUT |
| 10 | Integration test / simulation | To do | Resolve open questions 5, 10 first |
