# PPC Controller — Functional Description
## S7-1500 SCL Implementation

---

## 1. Overview

The Plant Power Controller (PPC) is implemented as a single Function Block (`FB_PPC_Controller`) that is called cyclically from OB30 (100 ms default). The FB orchestrates six Function Blocks (FCs) in a fixed execution order. Each FC is responsible for one well-defined control task; together they form a pipeline where each step feeds the next.

### Execution Pipeline

```
OB30 (every 100 ms)
  └── FB_PPC_Controller
        │
        ├─ ① FC_PPC_InverterMonitor     Scan inverters → N_Online, PmaxPlant, QmaxPlant
        ├─ ② FC_PPC_ModeManager         Watchdog + HMI → Plant_Mode (LOCAL/REMOTE/FALLBACK)
        ├─ ③ FC_PPC_RampControl         Rate-limit Cmd_P → Ramps_Pcmd
        ├─ ④ FC_PPC_PowerDistribution   Distribute Ramps_Pcmd by WAval → WSpt per inverter
        ├─ ⑤ FC_PPC_ReactiveControl     Distribute Q/PF by VArAval → VArSpt/PFSpt per inverter
        └─ ⑥ FC_PPC_FaultHandler        Override faulted inverters → OperMode/RemRdy_Spt
```

**Call order is mandatory.** Each FC reads outputs produced by the previous one. Reversing or skipping steps will produce incorrect or unsafe behaviour.

---

## 2. Data Architecture

### Inverter Array

The 10 inverters are stored as `PPC_Inverters: Array[0..9] of Inverter_controller` in DB39 (`PPC_Controller`). This array is passed as `VAR_IN_OUT` to each FC that iterates over inverters. A parallel set of named instances (`Inverter1..Inverter10`) exists in the same DB for HMI/SCADA visibility only — the PPC FCs write exclusively to the array.

### DB39 — PPC_Controller

Holds all plant-level configuration and working values. Key fields written by the FB each cycle:

| Field | Written by | Purpose |
|---|---|---|
| `Plant_N_Online` | FB (after ①) | Online inverter count — HMI display |
| `Limits_PmaxPlant` | FB (after ①) | Available P in kW — HMI display |
| `Limits_QmaxPlant` | FB (after ①) | Available Q in kVAr — HMI display |
| `Plant_Mode` | FB (after ②) | Current mode — HMI display |
| `Ramps_Pcmd` | FB (after ③) | Ramped P command — HMI trending |
| `AnyFault` | FB (after ⑥) | Plant-level fault flag — HMI alarm |

Configuration fields read by the FCs:

| Field | Used by | Description |
|---|---|---|
| `WRtg_kW` | ① | Rated kW per inverter (same for all) |
| `P_RampUp` | ③ | Max ramp-up rate in kW/s |
| `P_RampDown` | ③ | Max ramp-down rate in kW/s |

### UDT — Inverter_controller

Each element of `PPC_Inverters` holds both read (feedback) and write (setpoint) fields for one inverter:

| Field | Direction | Type | Description |
|---|---|---|---|
| `Enabled` | Read (config) | Bool | Operator-enabled in PPC |
| `RemReady` | Read (feedback) | Bool | Inverter reports remote-ready |
| `Error` | Read (feedback) | Bool | Active inverter fault |
| `CommError` | Read (comms block) | Bool | Modbus link broken |
| `WAval` | Read (feedback) | DInt | Available active power (pu × 10000) |
| `VArAval` | Read (feedback) | DInt | Available reactive power (pu × 10000) |
| `Wactive` | Read (feedback) | DInt | Measured active power (pu × 10000) |
| `Qactive` | Read (feedback) | DInt | Measured reactive power (pu × 10000) |
| `OperMode` | Write (setpoint) | DInt | InvOpMod: 308 = Operation, 303 = Stop |
| `WMode` | Write (setpoint) | DInt | GriMng.WMod: 303 = Off, 1079 = WCtlCom |
| `VArMode` | Write (setpoint) | DInt | GriMng.VArMod: 303 = Off, 1072 = VArCtlCom, 1075 = PFCtlCom |
| `WSpt` | Write (setpoint) | DInt | Active power setpoint (kW direct, FIX0) |
| `VArSpt` | Write (setpoint) | DInt | Reactive power setpoint (kVAr direct, FIX0) |
| `PFSpt` | Write (setpoint) | DInt | Power factor setpoint (PF × 10000, FIX4) |
| `PwrOffReas` | Read (feedback) | DInt | Inverter disconnect reason code |
| `DrtStt` | Read (feedback) | DInt | Derating state |

### Scaling Reference

| Signal | Raw register format | Physical unit | Conversion |
|---|---|---|---|
| WAval, VArAval | S32, FIX4, pu | kW / kVAr | raw ÷ 10000 × WRtg_kW |
| Wactive, Qactive | S32, FIX4, pu | kW / kVAr | raw ÷ 10000 × WRtg_kW |
| WSpt | S32, FIX0, kW | kW | direct integer |
| VArSpt | S32, FIX0, kVAr | kVAr | direct integer |
| PFSpt | S32, FIX4 | — | PF × 10000 (e.g. 0.950 → 9500) |

### SMA ENUM Reference

| Register | Value | Name | Meaning |
|---|---|---|---|
| InvOpMod (Holding 0) | 308 | Operation | Inverter running |
| InvOpMod (Holding 0) | 303 | Stop | Inverter stopped |
| RemRdy (Holding 2) | 308 | Ready | Remote-ready granted |
| RemRdy (Holding 2) | 303 | Standby | Remote-ready removed |
| GriMng.WMod (Holding 6) | 303 | Off | No active power control |
| GriMng.WMod (Holding 6) | 1079 | WCtlCom | Remote W setpoint active |
| GriMng.VArMod (Holding 4) | 303 | Off | No reactive control |
| GriMng.VArMod (Holding 4) | 1072 | VArCtlCom | Remote Q setpoint active |
| GriMng.VArMod (Holding 4) | 1075 | PFCtlCom | Remote PF setpoint active |

### SMA Start / Stop Interlock

The SMA inverter requires a specific sequence for starting and stopping via Modbus:

- **To start:** write `RemRdy = 308` (Ready) first, then `InvOpMod = 308` (Operation)
- **To stop:** write `InvOpMod = 303` (Stop); optionally also `RemRdy = 303` (Standby)
- **For active power control:** set `WMod = 1079` before writing `WSpt`
- **For reactive control:** set `VArMod = 1072` or `1075` before writing `VArSpt` / `PFSpt`

Writing only `WSpt = 0` without issuing a Stop command triggers PwrOffReas code 21626 ("Low Power SetPoint") and does not cleanly stop the inverter. Always use `InvOpMod = 303` for a clean stop.

---

## 3. Plant Operating Modes

| Mode | Value | Description |
|---|---|---|
| LOCAL | 0 | Operator controls targets from HMI. No upstream comms required. |
| REMOTE_IEC | 1 | Targets received from upstream SCADA / grid operator via comms thread. PPC actively controlling. |
| FALLBACK | 2 | Upstream comms lost (watchdog expired). PPC ramps all inverters to zero and stops them. |

### Mode Transitions

```
               LocalMode_Req = TRUE
    ┌─────────────────────────────────────────┐
    ▼                                         │
  LOCAL ◄──────────────────────────────── (any mode)

  LOCAL ──── comms healthy + EN_PPC ────► REMOTE_IEC

  REMOTE_IEC ──── watchdog expires ────► FALLBACK

  FALLBACK ──── comms restored ────────► REMOTE_IEC
```

---

## 4. FC Descriptions

---

### ① FC_PPC_InverterMonitor

**Purpose:** Scans all 10 inverters and produces the plant-level availability summary that all downstream FCs depend on.

**Inputs:**
| Parameter | Type | Source | Description |
|---|---|---|---|
| `WRtg_kW` | Real | DB39 | Rated power per inverter in kW |
| `Inverters` | Array IN_OUT | DB39 | Live 10-inverter array |

**Outputs:**
| Parameter | Type | Description |
|---|---|---|
| `N_Online` | Int | Count of inverters that passed all four online criteria |
| `PmaxPlant` | Real | Sum of available active power for online inverters (kW) |
| `QmaxPlant` | Real | Sum of available reactive power for online inverters (kVAr) |

**Online criteria — all four must be TRUE:**
1. `Enabled = TRUE` — operator has enabled this inverter in the PPC configuration
2. `RemReady = TRUE` — inverter feedback confirms it is in remote-ready state
3. `Error = FALSE` — no active inverter fault (ErrStt = Ok)
4. `CommError = FALSE` — Modbus communication is healthy (set by the comms block)

**Logic:**
```
N_Online  := 0
PmaxPlant := 0.0
QmaxPlant := 0.0

FOR i = 0 TO 9:
    IF online criteria met THEN
        N_Online  += 1
        PmaxPlant += WAval[i]  / 10000.0 × WRtg_kW     // pu → kW
        QmaxPlant += VArAval[i]/ 10000.0 × WRtg_kW     // pu → kVAr
    END_IF
```

**Why raw DInt for WAval/VArAval here but not in distribution FCs:**
In this FC, absolute kW/kVAr values are needed (PmaxPlant must be in kW so RampControl can clamp Ramps_Pcmd correctly). The ÷10000 × WRtg_kW conversion is therefore required here. In the distribution FCs, only ratios are needed — WRtg_kW cancels out.

---

### ② FC_PPC_ModeManager

**Purpose:** Determines `Plant_Mode` each cycle based on communication watchdog status and the HMI LOCAL override. Contains no timer logic — the TON timer lives in the FB static section and produces the `WD_Expired` boolean that is passed to this FC.

**Inputs:**
| Parameter | Type | Source | Description |
|---|---|---|---|
| `WD_Expired` | Bool | FB (from TON.Q) | TRUE when no watchdog edge received for > Watchdog_Timeout |
| `LocalMode_Req` | Bool | FB input | TRUE when HMI LOCAL/REMOTE selector is in LOCAL |

**In/Out:**
| Parameter | Type | Description |
|---|---|---|
| `Plant_Mode` | Int | Updated in place; persists in FB static between cycles |

**Logic — strict priority order:**

| Priority | Condition | Action |
|---|---|---|
| 1 (highest) | `LocalMode_Req = TRUE` | Set `Plant_Mode := 0` (LOCAL) and return |
| 2 | `WD_Expired = TRUE` | Set `Plant_Mode := 2` (FALLBACK) and return |
| 3 (default) | Neither above | Set `Plant_Mode := 1` (REMOTE_IEC) |

Priority 3 also handles automatic recovery from FALLBACK: once communication is restored and the watchdog timer resets, `WD_Expired` goes FALSE and the mode returns to REMOTE_IEC on the very next scan — no manual reset needed.

---

### ③ FC_PPC_RampControl

**Purpose:** Limits the rate of change of the active power command. Protects inverters, grid, and electrical infrastructure from abrupt generation steps.

**Inputs:**
| Parameter | Type | Source | Description |
|---|---|---|---|
| `Targets_P` | Real | FB input `Cmd_P` | Raw target from upstream (kW) |
| `PmaxPlant` | Real | From ① | Available plant power — upper clamp |
| `P_RampUp` | Real | DB39 | Maximum rate of increase (kW/s) |
| `P_RampDown` | Real | DB39 | Maximum rate of decrease (kW/s) |
| `dt` | Real | FB input `CycleTime_s` | OB30 cycle time in seconds (0.1 s) |
| `Plant_Mode` | Int | From ② | If FALLBACK (2), effective target forced to 0 |

**In/Out:**
| Parameter | Type | Description |
|---|---|---|
| `Ramps_Pcmd` | Real | Ramped command — accumulates between OB30 cycles |

**Logic:**
```
effectiveTarget := 0.0  if Plant_Mode = 2 (FALLBACK)
                := Targets_P  otherwise

delta := effectiveTarget - Ramps_Pcmd

IF delta > 0:
    Ramps_Pcmd += MIN(delta,  P_RampUp   × dt)   // climb at most P_RampUp kW/s
ELSIF delta < 0:
    Ramps_Pcmd -= MIN(|delta|, P_RampDown × dt)   // descend at most P_RampDown kW/s

Ramps_Pcmd := MIN(Ramps_Pcmd, PmaxPlant)          // never exceed available capacity
Ramps_Pcmd := MAX(Ramps_Pcmd, 0.0)                // PV cannot produce negative power
```

**Key note — Ramps_Pcmd must persist between cycles.** It is declared as a STAT variable in the FB and passed as VAR_IN_OUT. If it were a TEMP variable it would reset to zero every scan and no ramp would occur.

**FALLBACK ramp-down:** When mode switches to FALLBACK the effective target becomes 0. Ramps_Pcmd descends at P_RampDown kW/s until it reaches zero — the inverters reduce power gracefully rather than switching off abruptly.

---

### ④ FC_PPC_PowerDistribution

**Purpose:** Splits `Ramps_Pcmd` across all online inverters in proportion to each inverter's available active power (`WAval`). Writes `WSpt` and `WMode` to each inverter slot in the array.

**Inputs:**
| Parameter | Type | Source | Description |
|---|---|---|---|
| `Ramps_Pcmd` | Real | From ③ | Ramped P command to distribute (kW) |
| `Plant_Mode` | Int | From ② | If FALLBACK (2), FC returns immediately |

**In/Out:**
| Parameter | Type | Description |
|---|---|---|
| `Inverters` | Array | WSpt and WMode written per inverter |

**Algorithm — Proportional by WAval:**

```
// Pass 1: sum raw WAval integers across online inverters
sumWAval_raw := 0
FOR i = 0 TO 9:
    IF online THEN sumWAval_raw += WAval[i]

// Pass 2: write proportional setpoints
FOR i = 0 TO 9:
    IF online AND sumWAval_raw > 0 THEN
        share   = WAval[i] / sumWAval_raw        // dimensionless ratio
        WSpt[i] = REAL_TO_DINT(Ramps_Pcmd × share)
        WMode[i] = 1079  (WCtlCom)
    ELSE
        WSpt[i]  = 0
        WMode[i] = 303  (Off)
```

**Why raw DInt values for the ratio:**
WAval is stored as DInt in pu × 10000 format. When computing `WAval_i / Σ WAval_j`, the ÷10000 factor and the WRtg_kW rated-power factor both appear in numerator and denominator and cancel exactly. The share ratio is therefore identical whether computed from raw DInt values or from converted kW values — but using raw DInts avoids the floating-point conversion, keeps the code simpler, and remains correct even if WRtg_kW were different per inverter.

**Result:** Inverters with more available capacity receive a proportionally larger setpoint. An inverter derated to 60% of rated capacity receives 60% of the share of an un-derated inverter. Equal distribution is a special case where all WAval values happen to be equal.

**FALLBACK / ForceStop:** The FC returns at the top without writing anything when `Plant_Mode = 2`. FaultHandler (step ⑥) owns the safe-state writes.

---

### ⑤ FC_PPC_ReactiveControl

**Purpose:** Distributes reactive power or power factor setpoints to all online inverters according to the selected reactive control mode.

**Inputs:**
| Parameter | Type | Source | Description |
|---|---|---|---|
| `Plant_VArMode` | Int | FB input `Cmd_VArMode` | 0 = Off, 1 = Q, 2 = PF |
| `Targets_Q` | Real | FB input `Cmd_Q` | Total plant Q target in kVAr |
| `Targets_PF` | Real | FB input `Cmd_PF` | Power factor target (e.g. 0.95) |
| `Plant_Mode` | Int | From ② | If FALLBACK (2), FC returns immediately |

**In/Out:**
| Parameter | Type | Description |
|---|---|---|
| `Inverters` | Array | VArSpt, PFSpt and VArMode written per inverter |

**Mode 0 — Off:**
Sets `VArSpt = 0`, `PFSpt = 0`, `VArMode = 303` (Off) on all inverters. No reactive power contribution.

**Mode 1 — Q setpoint, proportional by VArAval:**
```
// Pre-sum
sumVArAval_raw := 0
FOR i = 0 TO 9: IF online THEN sumVArAval_raw += VArAval[i]

// Distribute
FOR i = 0 TO 9:
    IF online THEN
        share    = VArAval[i] / sumVArAval_raw   // dimensionless ratio
        VArSpt[i] = REAL_TO_DINT(Targets_Q × share)   // kVAr direct
        VArMode[i] = 1072  (VArCtlCom)
```
The same ratio principle applies as for WAval — raw DInt values cancel the scaling factor.

**Mode 2 — PF setpoint, uniform:**
```
FOR i = 0 TO 9:
    IF online THEN
        PFSpt[i]  = REAL_TO_DINT(Targets_PF × 10000)   // FIX4 scaling
        VArMode[i] = 1075  (PFCtlCom)
```

**Why uniform PF is correct for mode 2:** Power factor is a ratio (Q/S). When every inverter targets the same PF value, each one produces reactive power proportional to its active power output — reactive power is automatically distributed in proportion to each inverter's active generation. No per-inverter Q calculation is needed.

**Offline inverters (all modes):** `VArSpt = 0`, `PFSpt = 0`, `VArMode = 303`.

---

### ⑥ FC_PPC_FaultHandler

**Purpose:** Runs last in the chain. Overrides the setpoints written by FCs ④ and ⑤ for any inverter that is faulted, in comms error, or subject to a global stop command. Also manages the `OperMode` and `RemRdy_Spt` registers that control the SMA inverter run/stop state.

**Inputs:**
| Parameter | Type | Source | Description |
|---|---|---|---|
| `Plant_Mode` | Int | From ② | 2 = FALLBACK → stop all inverters |
| `ForceStop` | Bool | FB | TRUE when EN_PPC = FALSE |

**In/Out:**
| Parameter | Type | Description |
|---|---|---|
| `Inverters` | Array | OperMode, RemRdy_Spt (and setpoints for faulted units) written |
| `Ramps_Pcmd` | Real | Reset to 0.0 if all inverters are offline |

**Outputs:**
| Parameter | Type | Description |
|---|---|---|
| `AnyFault` | Bool | TRUE if any inverter has an active fault or comms error |

**Logic — per inverter, four cases:**

| Condition | Action |
|---|---|
| `ForceStop OR Plant_Mode = 2` | Write Stop to ALL inverters: OperMode=303, WSpt=0, VArSpt=0, WMode=303, VArMode=303. Comms block derives RemRdy=303 from OperMode. |
| `CommError = TRUE` | Same Stop writes as global stop; set AnyFault=TRUE. Best-effort — inverter's own watchdog will trip it if comms stay down. |
| `Error = TRUE` | Zero WSpt, VArSpt, PFSpt only; set AnyFault=TRUE. Do not stop healthy inverters — partial plant keeps running. |
| Healthy | Write OperMode=308. Comms block sees this and writes RemRdy=308 first, then InvOpMod=308 (SMA start interlock). Idempotent — safe every cycle. |

**RemRdy handling:** `RemRdy_Spt` is not a field in the `Inverter_controller` UDT. The comms block derives the required `RemRdy` register value from `OperMode`: when it prepares to write `InvOpMod=308` it first writes `RemRdy=308`; when it writes `InvOpMod=303` it also writes `RemRdy=303`. This keeps the SMA start/stop interlock in the comms layer without requiring an extra UDT field.

**Why writing OperMode=308 every cycle to healthy inverters is safe:**
The SMA inverter ignores re-writes of its current state. Writing 308 when already in Operation has no effect. Writing 308 after a recovery (inverter was stopped) re-starts it without any manual intervention.

**Ramps_Pcmd reset:**
If the online inverter count drops to zero (all stopped, faulted, or disabled), `Ramps_Pcmd` is reset to 0.0. This ensures that when inverters come back online they receive setpoints that ramp up from zero at the configured P_RampUp rate, rather than jumping to whatever large value Ramps_Pcmd had accumulated.

---

## 5. FB_PPC_Controller

**Purpose:** Main orchestrator block. Holds timer state, detects the watchdog edge, copies FB inputs to the working variables used by the FCs, calls all six FCs in order, mirrors results to DB39 for HMI, and writes the three FB output variables.

### Interface

**Inputs (set by OB30 caller):**

| Variable | Type | Description |
|---|---|---|
| `EN_PPC` | Bool | Master enable. FALSE → immediate safe state |
| `IEC_Watchdog` | Bool | Heartbeat toggle from upstream comms thread |
| `CycleTime_s` | Real | OB30 cycle time in seconds (set to 0.1 for 100 ms) |
| `Cmd_P` | Real | Active power target from upstream (kW) |
| `Cmd_Q` | Real | Reactive power target from upstream (kVAr) |
| `Cmd_PF` | Real | Power factor target from upstream (e.g. 0.95) |
| `Cmd_VArMode` | Int | Reactive mode: 0 = Off / 1 = Q / 2 = PF |
| `LocalMode_Req` | Bool | HMI LOCAL override (TRUE = force LOCAL mode) |

**Outputs (to HMI and SCADA):**

| Variable | Type | Description |
|---|---|---|
| `PPC_Active` | Bool | TRUE when Plant_Mode = 1 (REMOTE_IEC) |
| `PPC_Fault` | Bool | TRUE when any inverter fault is active |
| `Mode_Out` | Int | Current Plant_Mode (0 / 1 / 2) |

**Static variables (retained between OB30 cycles):**

| Variable | Type | Description |
|---|---|---|
| `Watchdog_TON` | TON | Timer instance; counts time since last watchdog edge |
| `Watchdog_LastBit` | Bool | Previous value of IEC_Watchdog for edge detection |
| `Watchdog_Timeout` | Time | Timeout period, default T#30S (configurable) |
| `Plant_Mode` | Int | Current mode, persists between cycles |
| `Ramps_Pcmd` | Real | Ramped P command, accumulates between cycles |

### Watchdog Logic

The upstream comms thread toggles `IEC_Watchdog` once per received telegram. The FB detects each rising edge (0→1 transition) and uses it to reset the TON timer. If no edge arrives within `Watchdog_Timeout`, `TON.Q` goes TRUE and ModeManager switches to FALLBACK.

```
Edge detected (IEC_Watchdog AND NOT LastBit)?
    YES → call TON with IN=FALSE    (reset timer to zero)
    NO  → call TON with IN=TRUE     (let timer count up)

WD_Expired := TON.Q                 (TRUE when no telegram for > Watchdog_Timeout)
```

Calling `TON(IN=FALSE)` for a single scan resets `ET` to zero and clears `Q`. The next scan `IN` returns to TRUE and the timer restarts from zero. This achieves a clean restart on every received telegram.

### EN_PPC = FALSE Guard

When the master enable is FALSE, the FB calls FaultHandler with `ForceStop=TRUE` (which stops all inverters), resets `Plant_Mode` to 0 and `Ramps_Pcmd` to 0.0, writes the outputs, and returns immediately without calling any other FC.

### DB39 Mirror Writes

After each FC call, the FB writes key internal values back to DB39 so the HMI can trend and display them without needing access to the FB instance DB:

| After FC | Value mirrored to DB39 |
|---|---|
| ① InverterMonitor | Plant_N_Online, Limits_PmaxPlant, Limits_QmaxPlant |
| ② ModeManager | Plant_Mode |
| ③ RampControl | Ramps_Pcmd |
| ⑥ FaultHandler | AnyFault |

---

## 6. Comms Layer Separation

The PPC FCs write only to UDT fields in the `PPC_Inverters` array (e.g. `WSpt`, `WMode`, `OperMode`, `RemRdy_Spt`). A separate Modbus comms block — outside the PPC FB — reads these fields and maps them to the actual Modbus holding register writes (FC16) each cycle. Feedback values (`WAval`, `VArAval`, `Wactive`, `RemReady`, `Error`, etc.) are read from the inverter input registers (FC04) by the same comms block and written into the UDT.

This separation means:
- The PPC logic is completely independent of register addresses
- The comms block can be updated (e.g. different Modbus unit IDs or register offsets) without touching any PPC FC
- The PPC FCs can be tested in simulation by driving the UDT fields directly

---

## 7. Implementation Checklist

| Step | Item | Status |
|---|---|---|
| 1 | UDT `Inverter_controller` — add `RemRdy_Spt: DInt` field | To verify |
| 2 | DB39 `PPC_Controller` — add `WRtg_kW`, `Limits_QmaxPlant`, `Plant_VArMode`, `AnyFault` | To verify |
| 3 | Import and compile `FC_PPC_InverterMonitor` | To do |
| 4 | Import and compile `FC_PPC_ModeManager` | To do |
| 5 | Import and compile `FC_PPC_RampControl` | To do |
| 6 | Import and compile `FC_PPC_PowerDistribution` | To do |
| 7 | Import and compile `FC_PPC_ReactiveControl` | To do |
| 8 | Import and compile `FC_PPC_FaultHandler` | To do |
| 9 | Import and compile `FB_PPC_Controller` | To do |
| 10 | Place FB call in OB30; wire EN_PPC, IEC_Watchdog, Cmd_P/Q/PF inputs | To do |
| 11 | Configure OB30 cycle time; set `CycleTime_s = 0.1` in FB call | To do |
| 12 | Set `WRtg_kW` in DB39 from SMA register 184 at commissioning | To do |
| 13 | Configure `P_RampUp`, `P_RampDown` in DB39 per plant requirements | To do |
| 14 | Commission Modbus comms block; verify UDT field mapping to registers | To do |
| 15 | Simulation / FAT: test all three modes and fault scenarios | To do |
