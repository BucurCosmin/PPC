# PPC Controller Design — S7-1500 SCL

## Overview

Plant Power Controller (PPC) for SMA Sunny Central inverter plant running on Siemens S7-1500.
Implementation language: SCL. Structure: one main **FB** calling multiple **FCs/FBs** for maintainability.
Grid-code compliance: ANRE Ordinul 51/2019, ANRE Ordinul 60/2024, Category D.

---

## Data Structures

### UDT: `Inverter_controller`

| Field | Type | Direction | Description |
|---|---|---|---|
| Enabled | Bool | Config (operator) | Inverter enabled in PPC — never overwritten by automatic logic |
| RemReady | Bool | Feedback | Inverter reports remote-ready |
| Error | Bool | Feedback | Active inverter fault |
| CommError | Bool | Comms block | Modbus link broken |
| Available | Bool | Computed | Combined online criteria (step ①). Single source of truth for all downstream FCs |
| OperMode | DInt | Write | InvOpMod setpoint (308=Operation, 303=Stop) |
| Wactive | DInt | Feedback | Measured active power (pu×10000, FIX4) |
| Qactive | DInt | Feedback | Measured reactive power (pu×10000, FIX4) |
| WMode | DInt | Write | GriMng.WMod (1079=WCtlCom, 303=Off) |
| VArMode | DInt | Write | GriMng.VArMod (1072=VArCtlCom, 1075=PFCtlCom, 303=Off) |
| WSpt | DInt | Write | Active power setpoint (kW direct, FIX0) |
| VArSpt | DInt | Write | Reactive power setpoint (kVAr direct, FIX0) |
| PFSpt | DInt | Write | Power factor setpoint (PF×10000, FIX4) |
| WAval | DInt | Feedback | Available active power (pu×10000, FIX4) |
| VArAval | DInt | Feedback | Available reactive power (pu×10000, FIX4) |
| PwrOffReas | DInt | Feedback | Power-off reason code |
| DrtStt | DInt | Feedback | Derating state |
| ErrClr | DInt | Write | Fault acknowledge (26=Ackn one-shot, 0=idle) |

### UDT: `Skid_Electric_Status`

| Field | Type | Description |
|---|---|---|
| Sep_Cel1 | Bool | Output cell 1 separator — TRUE = closed |
| Clp_Cel1 | Bool | Output cell 1 earthing switch — TRUE = closed (earthed) |
| Sep_Cel2 | Bool | Output cell 2 separator — TRUE = closed |
| Clp_Cel2 | Bool | Output cell 2 earthing switch — TRUE = closed (earthed) |
| Intrerup_CelTraf | Bool | Transformer cell breaker — TRUE = closed |
| Sep_CelTraf | Bool | Transformer cell separator — TRUE = closed |
| Clp_CelTraf | Bool | Transformer cell earthing switch — TRUE = closed (earthed) |
| Cel1_OK | Bool | Computed: Sep_Cel1 AND NOT Clp_Cel1 |
| Cel2_OK | Bool | Computed: Sep_Cel2 AND NOT Clp_Cel2 |
| CelTraf_OK | Bool | Computed: Intrerup AND Sep AND NOT Clp |
| ELECTRIC_OK | Bool | Computed: Cel1_OK AND Cel2_OK AND CelTraf_OK |

### UDT: `UDT_PQ_CapPoint`

| Field | Type | Description |
|---|---|---|
| P_pct | Real | % of rated power (configure as 0, 25, 50, 75, 100) |
| Q_ind_max | Real | kVAr, inductive (lagging/underexcited) Q limit at this P tier |
| Q_cap_max | Real | kVAr, capacitive (leading/overexcited) Q limit at this P tier |

---

## DB39: `PPC_Controller`

### Inverter references

- `Inverters.PPC_Inverters`: `Array[0..9] of Inverter_controller` — written by PPC FCs; passed as VAR_IN_OUT
- `Inverter1..Inverter10`: Named instances for HMI/SCADA visibility only (read mirrors, not written by PPC)

### Plant-level fields

| Field | Type | Unit | Written by | Description |
|---|---|---|---|---|
| WRtg_kW | Real | kW | Config | Rated active power per inverter |
| P_RampUp | Real | kW/s | Config | Max active power ramp-up rate |
| P_RampDown | Real | kW/s | Config | Max active power ramp-down rate |
| Plant_N_Online | Int | — | FB after ① | Online inverter count |
| Limits_PmaxPlant | Real | kW | FB after ① | Available plant active power |
| Limits_QmaxPlant | Real | kVAr | FB after ① | Available plant reactive power |
| Plant_Mode | Int | — | FB after ② | 0=LOCAL / 1=REMOTE_IEC / 2=FALLBACK |
| Ramps_Pcmd | Real | kW | FB after ③ | Ramped P command (HMI trending) |
| AnyFault | Bool | — | FB after ⑧ | Any inverter fault active |
| AnyDerating | Bool | — | FB after ⑧ | Any derating state active |
| FaultMask | Word | — | FB after ⑧ | Bit i = inverter i faulted |
| Ramps_Qcmd | Real | kVAr | FB after ⑤ | Q ramp accumulator mirror (lives in QCap_IDB.Ramps_Qcmd) |

### Frequency response parameters (ANRE Ord 51/2019, SCADA-writable)

| Field | Type | Default | Description |
|---|---|---|---|
| f_nom | Real | 50.0 | Hz, nominal grid frequency |
| Pn_MW | Real | 48.0 | MW, plant nominal rated power |
| Droop_pct | Real | 8.0 | %, droop setting (ISCE tests at 8.0 and 10.0) |
| DeadBand_mHz | Real | 200.0 | mHz, dead band (0 for Art.117 fine-response sub-test) |
| Pmin_stab | Real | 0.0 | kW, minimum stable power |
| OFRT_Trip_Hz | Real | 51.5 | Hz, over-frequency trip threshold |
| UFRT_Trip_Hz | Real | 47.5 | Hz, under-frequency trip threshold |
| Reconnect_Enable | Bool | — | Rising edge clears frequency trip latch |

### Frequency response diagnostics (SCADA-readable, ISCE acquisition)

| Field | Type | Description |
|---|---|---|
| dP_droop | Real | kW, droop correction term (ISCE live signal) |
| FreqResp_Pmin | Real | kW, dynamic Pmin_active |
| FreqResp_Pmax | Real | kW, dynamic Pmax_active |
| Trip_FreqFault | Bool | Frequency trip active alarm |
| Reconnecting | Bool | Trip cleared, ramping back to full power |
| Reconnect_Timer_s | Real | s, reconnect duration (ISCE Test 7 timing) |

### Q capability parameters (ANRE Ord 51/2019, SCADA-writable)

| Field | Type | Default | Description |
|---|---|---|---|
| VArControl_Mode | Int | 0 | 0=fixed Q, 1=U droop, 2=off (separate from Plant_VArMode) |
| U_setpoint_ext | Real | — | kV, voltage setpoint for U droop mode |
| U_Droop_pct | Real | 5.0 | %, voltage droop gain |
| Q_Ramp_Rate_fast | Real | — | kVAr/s, fast Q ramp (ISCE Test 6) |
| Q_Ramp_Rate_slow | Real | — | kVAr/s, slow Q ramp (ISCE Test 6) |
| Q_Ramp_Fast_Sel | Bool | — | FALSE=slow, TRUE=fast |

### Q capability diagnostics (SCADA-readable, ISCE Test 8/9)

| Field | Type | Description |
|---|---|---|
| Q_max_inductive | Real | kVAr, P-Q capability inductive limit at current P |
| Q_max_capacitive | Real | kVAr, P-Q capability capacitive limit at current P |
| Q_limited | Bool | TRUE when Q clamped by P-Q capability envelope |

---

## Architecture

```
OB30 (every 100 ms)
  │
  ├─ 10× FC_SkidElectricStatus    // DI → SKID_ELECTRIC.Skids[0..9].ELECTRIC_OK
  ├─ 10× FC_PPC_SkidMapping       // Modbus bridge
  │
  └─ FB_PPC_Controller
        │
        ├─ ①  FC_PPC_InverterMonitor    → N_Online, PmaxPlant, QmaxPlant, Inverters[i].Available
        ├─ ②  FC_PPC_ModeManager        → Plant_Mode (LOCAL / REMOTE_IEC / FALLBACK)
        ├─ ③  FC_PPC_RampControl        → Ramps_Pcmd (rate-limits AGC Cmd_P changes only)
        ├─ ④  FB_PPC_FreqResponse       → P_final_kW (droop correction added POST-ramp)
        │        └─ if Trip_FreqFault: P_final_kW = 0 AND Ramps_Pcmd reset to 0
        ├─ ⑤  FB_PPC_QCapability        → Q_final_kVAr (P-Q clamp + Q ramp + U droop)
        ├─ ⑥  FC_PPC_PowerDistribution  → WSpt, WMode per inverter (input = P_final_kW)
        ├─ ⑦  FC_PPC_ReactiveControl    → VArSpt/PFSpt/VArMode per inverter (input = Q_final_kVAr)
        └─ ⑧  FC_PPC_FaultHandler       → OperMode overrides; AnyFault, AnyDerating, FaultMask
```

**Call order is mandatory.** Each step feeds the next. Steps ④ and ⑤ are FBs (retain state between OB30 cycles); steps ①②③⑥⑦⑧ are FCs (stateless).

---

## Operating Modes

| Mode | Value | Description |
|---|---|---|
| LOCAL | 0 | Targets from HMI; no upstream comms required |
| REMOTE_IEC | 1 | Targets from SCADA/grid operator; PPC active |
| FALLBACK | 2 | Comms lost (watchdog expired); all inverters ramped to zero |

---

## FC/FB Specifications

### FC_PPC_InverterMonitor (step ①)

Scans all 10 inverters. Computes `Inverters[i].Available` (6-condition check) — the single source of truth consumed by all downstream FCs.

**6 online conditions (ALL must be TRUE):**
1. `Enabled` — operator enabled
2. `RemReady` — inverter in remote-ready state
3. `NOT Error` — no active fault
4. `NOT CommError` — Modbus link healthy
5. `PwrOffReas = 0` — no abnormal disconnect
6. `SKID_ELECTRIC.Skids[i].ELECTRIC_OK` — switchgear in deliverable state

**Outputs:** `N_Online`, `PmaxPlant` (sum of WAval×WRtg_kW for available inverters), `QmaxPlant` (sum of VArAval×WRtg_kW).

---

### FC_PPC_ModeManager (step ②)

Evaluates watchdog and HMI selector → sets `Plant_Mode`. Priority: LOCAL > FALLBACK > REMOTE_IEC. Recovery from FALLBACK is automatic when watchdog resets.

---

### FC_PPC_RampControl (step ③)

Rate-limits the AGC `Cmd_P` input only. Produces `Ramps_Pcmd` — the smoothed base command that feeds into step ④.

**Does NOT limit frequency droop response** — droop is added in step ④ after this FC.

---

### FB_PPC_FreqResponse (step ④) — ANRE Ord 51/2019 Art. 114–120

**Purpose:** Primary frequency response (RFA). Adds droop correction POST-ramp so frequency events are immediate — not rate-capped by RampControl.

**Droop formula:**
```
df      = f_active − f_nom
dP_droop = −(2 × Pn_kW × df) / Droop_pct     [kW]
P_final_kW = LIMIT(Pmin_active, Ramps_Pcmd + dP_droop, Pmax_active)
```

**Dynamic band (Note 1, ISCE test program):**
```
dP_at_200mHz = (2 × Pn_kW × 0.200) / Droop_pct
Pmin_active  = Pmin_stab + dP_at_200mHz
Pmax_active  = Pmax_disp − dP_at_200mHz          [Pmax_disp = PmaxPlant]
```

**Dead band:** `|df| ≤ DeadBand_mHz / 1000` → `dP_droop = 0`. Hard cutout (not soft blend). Set `DeadBand_mHz = 0` for Art.117 fine-response test.

**Frequency source:** `Frequency_Source_Sel = FALSE` → use `f_meas` (real AI); `TRUE` → use `Freq_Test_Override` (ISCE 4–20 mA test bench). Both SCADA-writable.

**Trip logic:** `Trip_FreqFault` latches when `f > OFRT_Trip_Hz (51.5 Hz)` or `f < UFRT_Trip_Hz (47.5 Hz)`. When tripped: `P_final_kW = 0`. **Does NOT trip a breaker** — only zeros inverter setpoints. Caller (FB_PPC_Controller) also resets `Ramps_Pcmd := 0` so reconnect ramp-up starts from zero. Trip clears on `Reconnect_Enable` rising edge with f in normal band.

**Reconnect timer:** `Reconnect_Timer_s` measures time from trip-clear to P reaching 95% Pmax_active — required for ISCE Test 7.

**State retained:** `Trip_Latch : Bool`, `Reconnect_TON : TON`, `Reconnect_LastEnable : Bool`.

---

### FB_PPC_QCapability (step ⑤) — ANRE Ord 51/2019 Art. 147, 150, 152, 160, 163

**Purpose:** Generates plant-level Q command after P-Q capability clamping and Q ramp limiting. Output `Q_final_kVAr` feeds step ⑦.

**P-Q capability (Test 8):** `PQ_Table[0..4]` of `UDT_PQ_CapPoint` stored in instance DB (configure from HMI). 5 tiers at P = 0/25/50/75/100% of `Pmax_kW`. Current Q limits computed by linear interpolation at the actual `P_actual_kW / Pmax_kW` operating point. `Q_setpoint_final` clamped to `[−Q_ind_max, +Q_cap_max]` regardless of control mode.

**Q ramp (Test 6):** Rate-limited accumulator `Ramps_Qcmd` (static, moved from FC_PPC_ReactiveControl). Two independently-selectable speeds: `Q_Ramp_Rate_fast` / `Q_Ramp_Rate_slow`, switched via `Q_Ramp_Fast_Sel`. In FALLBACK: effective target forced to 0 → Q ramps down gracefully.

**Control modes (VArControl_Mode — separate from Plant_VArMode):**
- `0` = Fixed Q: ramp `Q_setpoint_ext` → P-Q clamp → `Q_final_kVAr`
- `1` = Voltage droop (Test 9): `Q = (dU_pu / (U_Droop_pct/100)) × QmaxPlant` → ramp → clamp
- `2` = Off: `Q_final_kVAr = 0` (used when `Plant_VArMode = 2` PF in ReactiveControl)

**Voltage droop gain:** `dU_pu = (U_setpoint_ext − U_meas) / U_meas`. Gain scales with `QmaxPlant` (adaptive to actual inverter capacity). Example: U_Droop_pct=5%, dU=2.5% → Q = 50% of QmaxPlant.

**Zero-P reactive (Test 10):** Q dispatch is NOT gated on P > 0. Inverters with `OperMode=308` (maintained by FaultHandler) can source/sink Q even when `WSpt = 0`.

**State retained:** `Ramps_Qcmd : Real`, `PQ_Table : Array[0..4] of UDT_PQ_CapPoint`.

---

### FC_PPC_PowerDistribution (step ⑥)

Distributes `P_final_kW` (from step ④ — droop-corrected) across available inverters proportionally by WAval. Writes `WSpt` and `WMode=1079` per inverter. Returns immediately in FALLBACK. Per-inverter WSpt clamp: `maxWSpt = WAval_i/10000 × WRtg_kW`.

---

### FC_PPC_ReactiveControl (step ⑦)

Distributes `Q_final_kVAr` (from step ⑤ — already ramped and P-Q clamped) across available inverters proportionally by VArAval. **Q ramp has been removed** — it is now owned by FB_PPC_QCapability. Writes `VArSpt`, `PFSpt`, `VArMode` per inverter.

**Modes (Plant_VArMode):**
- `0` = Off: VArSpt=0, VArMode=303
- `1` = Q control: distribute `Q_final_kVAr` by VArAval share; VArMode=1072
- `2` = PF uniform: write `Targets_PF × 10000` to all available inverters; VArMode=1075

---

### FC_PPC_FaultHandler (step ⑧)

Overrides setpoints for faulted / FALLBACK / disconnected inverters. Maintains `OperMode=308` for healthy inverters. Handles ErrClr one-shot. Resets `Ramps_Pcmd` and `QCap_IDB.Ramps_Qcmd` when all inverters are offline. `NOT ELECTRIC_OK` treated same as `PwrOffReas ≠ 0`: zero setpoints, `AnyFault=TRUE`, keep `OperMode=308` for instant recovery.

---

## Scaling Conventions

| Signal | Register format | PLC unit | Conversion |
|---|---|---|---|
| WAval, VArAval | S32, FIX4, pu | pu×10000 | ÷10000 × WRtg_kW → kW/kVAr |
| Wactive, Qactive | S32, FIX4, pu | pu×10000 | ÷10000 × WRtg_kW → kW/kVAr |
| WSpt | S32, FIX0, kW | kW | direct integer |
| VArSpt | S32, FIX0, kVAr | kVAr | direct integer |
| PFSpt | S32, FIX4 | — | PF × 10000 (0.950 → 9500) |
| P_actual_kW | External meter AI | kW | 4–20 mA → kW scaling at AI block |
| f_meas | Frequency transducer AI | Hz | 4–20 mA → Hz scaling |
| U_meas | VT on MV bus | kV | Analog input |

---

## File Structure

```
PLC_1 [S7-1500]
├── Program blocks
│   ├── FB_PPC_Controller         [FB, SCL]  — main orchestrator
│   ├── FC_PPC_InverterMonitor    [FC, SCL]  — ①
│   ├── FC_PPC_ModeManager        [FC, SCL]  — ②
│   ├── FC_PPC_RampControl        [FC, SCL]  — ③
│   ├── FB_PPC_FreqResponse       [FB, SCL]  — ④ P-f droop (ANRE Art.114–120)
│   ├── FB_PPC_QCapability        [FB, SCL]  — ⑤ P-Q capability + Q ramp (ANRE Art.147–163)
│   ├── FC_PPC_PowerDistribution  [FC, SCL]  — ⑥
│   ├── FC_PPC_ReactiveControl    [FC, SCL]  — ⑦
│   ├── FC_PPC_FaultHandler       [FC, SCL]  — ⑧
│   ├── FC_SkidElectricStatus     [FC, SCL]  — DI → ELECTRIC_OK per skid
│   └── FC_PPC_SkidMapping        [FC, SCL]  — Modbus bridge
├── PLC data types
│   ├── Inverter_controller        [UDT]
│   ├── Skid_Electric_Status       [UDT]
│   └── UDT_PQ_CapPoint            [UDT]  — P-Q capability table entry
└── Data blocks
    ├── PPC_Controller             [DB39]  — plant-level config + working values
    └── SKID_ELECTRIC              [DB]    — Skids: Array[0..9] of Skid_Electric_Status
```

---

## SMA ENUM Reference

| Register | ENUM value | Name | Meaning |
|---|---|---|---|
| InvOpMod (Holding 0) | 308 | Operation | Inverter running — write to start |
| InvOpMod (Holding 0) | 303 | Stop/Off | Safe-state stop |
| RemRdy (Holding 2) | 308 | Ready | Remote-ready state |
| RemRdy (Holding 2) | 303 | Standby | Remove remote-ready |
| GriMng.WMod (Holding 6) | 303 | Off | No active power control |
| GriMng.WMod (Holding 6) | 1079 | WCtlCom | Remote W setpoint via Modbus |
| GriMng.VArMod (Holding 4) | 303 | Off | No reactive power control |
| GriMng.VArMod (Holding 4) | 1072 | VArCtlCom | Remote Q setpoint via Modbus |
| GriMng.VArMod (Holding 4) | 1075 | PFCtlCom | Remote PF setpoint via Modbus |

**Start/Stop interlock:** write `RemRdy=308` then `InvOpMod=308` to start; `InvOpMod=303` to stop.

---

## ANRE Test Compliance Map

| ISCE Test | Article | Block | Configurable parameter |
|---|---|---|---|
| Test 1/2/3 (P-f over/under-freq droop) | Art. 114–120 | FB_PPC_FreqResponse | Droop_pct, DeadBand_mHz |
| Test 3 (fine response Art.117) | Art. 117 | FB_PPC_FreqResponse | DeadBand_mHz = 0 via SCADA |
| Test 4 (full sweep + trip + reconnect) | Art. 118–120 | FB_PPC_FreqResponse | OFRT_Trip_Hz, Reconnect_Enable |
| Test 6 (Q ramp rates) | — | FB_PPC_QCapability | Q_Ramp_Rate_fast/slow, Q_Ramp_Fast_Sel |
| Test 7 (reconnect timing) | Art. 126–131 | FB_PPC_FreqResponse | Reconnect_Timer_s (read from SCADA) |
| Test 8 (P-Q diagram, 5 tiers) | Art. 147, 152 | FB_PPC_QCapability | PQ_Table[0..4] in instance DB |
| Test 9 (voltage droop Q control) | Art. 160, 163 | FB_PPC_QCapability | VArControl_Mode=1, U_Droop_pct |
| Test 10 (Q at P=0, ≥30 min) | Art. 150, 152 | FC_PPC_ReactiveControl | No gate on P>0; OperMode=308 maintained |
| Test 12 (SCADA data exchange) | Art. 164–165 | DB39 fields | All diagnostic outputs in DB39 |

---

## Open Questions / To Confirm

| # | Question | Status |
|---|---|---|
| 1 | SMA WAval/WSpt scaling | **RESOLVED** — WAval/VArAval FIX4; WSpt FIX0; PFSpt FIX4×10000 |
| 2 | OperMode ENUM | **RESOLVED** — 308=Operation, 303=Stop |
| 3 | WMode ENUM | **RESOLVED** — 303=Off, 1079=WCtlCom |
| 4 | VArMode ENUM | **RESOLVED** — 303=Off, 1072=VArCtlCom, 1075=PFCtlCom |
| 5 | Distribution algorithm | **RESOLVED** — proportional WAval (P) / VArAval (Q) |
| 6 | Fallback P level | **RESOLVED** — 0 via InvOpMod=303 |
| 7 | SKID_ELECTRIC polarity | **PENDING** — verify auxiliary contact wiring (closed=TRUE assumed) |
| 8 | PQ_Table values | **PENDING** — enter from inverter datasheets before ISCE Test 8 |
| 9 | P_actual_kW source | **PENDING** — wire from POD meter AI at commissioning |
| 10 | f_meas AI scaling | **PENDING** — configure 4–20 mA → 47.5–52.0 Hz at AI block |
| 11 | Q_Ramp_Rate_fast/slow values | **PENDING** — enter grid code requirements before ISCE Test 6 |
