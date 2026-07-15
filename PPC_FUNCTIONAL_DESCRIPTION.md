# PPC Controller — Functional Description
## S7-1500 SCL Implementation | ANRE Ord 51/2019 + Ord 60/2024 Compliant

---

## 1. Overview

The Plant Power Controller (PPC) is implemented as a single Function Block (`FB_PPC_Controller`) called cyclically from OB30 (100 ms default). It orchestrates eight FCs/FBs in a fixed execution order, forming a pipeline where each step feeds the next.

### Execution Pipeline

```
OB30 (every 100 ms)
  │
  ├── 10× FC_SkidElectricStatus   Hardwired DI → SKID_ELECTRIC.Skids[i].ELECTRIC_OK
  ├── 10× FC_PPC_SkidMapping      Modbus data bridge (existing)
  │
  └── FB_PPC_Controller
        │
        ├─ ①  FC_PPC_InverterMonitor    Scan inverters → N_Online, PmaxPlant, QmaxPlant,
        │                                Inverters[i].Available (6-condition, single source)
        ├─ ②  FC_PPC_ModeManager        Watchdog + HMI → Plant_Mode (LOCAL/REMOTE/FALLBACK)
        ├─ ③  FC_PPC_RampControl        Rate-limit AGC Cmd_P → Ramps_Pcmd
        ├─ ④  FB_PPC_FreqResponse       P-f droop → P_final_kW  [post-ramp, not rate-limited]
        │                                Trip_FreqFault: P=0 + Ramps_Pcmd reset
        ├─ ⑤  FB_PPC_QCapability        P-Q capability clamp + Q ramp → Q_final_kVAr
        ├─ ⑥  FC_PPC_PowerDistribution  Distribute P_final_kW by WAval → WSpt per inverter
        ├─ ⑦  FC_PPC_ReactiveControl    Distribute Q_final_kVAr by VArAval → VArSpt per inverter
        └─ ⑧  FC_PPC_FaultHandler       Fault overrides → OperMode, ErrClr; AnyFault, FaultMask
```

**Call order is mandatory.** Reversing or skipping steps produces incorrect or unsafe behaviour.

**Architecture principle — droop post-ramp:**
Steps ③ and ④ are deliberately separate. `FC_PPC_RampControl` (step ③) limits rate of change for normal AGC setpoint changes. `FB_PPC_FreqResponse` (step ④) adds the droop correction *after* the ramp — so frequency events are immediate, never capped by the ramp rate. This satisfies ANRE primary frequency response timing requirements.

---

## 2. Data Architecture

### Inverter Array

The 10 inverters are `PPC_Inverters: Array[0..9] of Inverter_controller` in DB39 (`PPC_Controller`). Passed as `VAR_IN_OUT` to each FC/FB that iterates over inverters. Named instances `Inverter1..Inverter10` exist in the same DB for HMI/SCADA read access only — PPC FCs write exclusively to the array.

### DB39 — PPC_Controller

**Working values (written each cycle):**

| Field | Written by | Description |
|---|---|---|
| Plant_N_Online | FB after ① | Online inverter count — HMI display |
| Limits_PmaxPlant | FB after ① | Available P in kW — HMI / RampControl input |
| Limits_QmaxPlant | FB after ① | Available Q in kVAr — HMI / QCapability input |
| Plant_Mode | FB after ② | Current mode (0/1/2) — HMI display |
| Ramps_Pcmd | FB after ③ | Ramped P command — HMI trending |
| dP_droop | FB after ④ | Droop correction kW — ISCE acquisition |
| FreqResp_Pmin | FB after ④ | Dynamic Pmin_active — ISCE acquisition |
| FreqResp_Pmax | FB after ④ | Dynamic Pmax_active — ISCE acquisition |
| Trip_FreqFault | FB after ④ | Frequency trip alarm — SCADA |
| Reconnecting | FB after ④ | Recovery in progress — SCADA |
| Reconnect_Timer_s | FB after ④ | Reconnect duration s — ISCE Test 7 |
| Q_max_inductive | FB after ⑤ | Current Q inductive capability kVAr — ISCE Test 8 |
| Q_max_capacitive | FB after ⑤ | Current Q capacitive capability kVAr — ISCE Test 8 |
| Q_limited | FB after ⑤ | Q was clamped by ANRE Stage 1 P-Q table — SCADA alarm |
| SMA_Qmax_plant | FB after ⑤ | kVAr, SMA physical Q limit at current P/U — Stage 2 diagnostic |
| Q_SMA_limited | FB after ⑤ | TRUE when Q clamped by SMA physical envelope (Stage 2) — SCADA alarm |
| Ramps_Qcmd | FB after ⑤ | Q ramp accumulator mirror — HMI trending |
| AnyFault | FB after ⑧ | Plant-level fault flag — HMI alarm |
| AnyDerating | FB after ⑧ | Derating state flag — HMI alarm |
| FaultMask | FB after ⑧ | Per-inverter fault bitmap — HMI |

**Configuration fields (SCADA-writable, read by FCs):**

| Field | Used by | Default | Description |
|---|---|---|---|
| WRtg_kW | ① | — | Rated kW per inverter |
| P_RampUp | ③ | — | Max ramp-up rate kW/s |
| P_RampDown | ③ | — | Max ramp-down rate kW/s |
| f_nom | ④ | 50.0 | Hz, nominal frequency |
| Pn_MW | ④⑤ | 46.0 | MW, plant nominal rated power (10 × SMA SC 4600 UP) |
| Droop_OF_pct | ④ | 8.0 | %, over-frequency droop (Art. 114-115, ANRE Ord.51/2019) |
| Droop_UF_pct | ④ | 10.0 | %, under-frequency droop (Art. 118-120, ANRE Ord.51/2019) |
| DeadBand_mHz | ④ | 200.0 | mHz, dead band (0 for Art.117 test) |
| Pmin_stab | ④ | 0.0 | kW, minimum stable power |
| OFRT_Trip_Hz | ④ | 51.5 | Hz, over-frequency trip |
| UFRT_Trip_Hz | ④ | 47.5 | Hz, under-frequency trip |
| Reconnect_Enable | ④ | — | Clears freq trip latch (operator) |
| VArControl_Mode | ⑤ | 0 | 0=fixed Q, 1=U droop, 2=off, 3=U Control PID |
| U_setpoint_ext | ⑤ | — | kV, voltage setpoint — modes 1 (droop) and 3 (PID) |
| U_Droop_pct | ⑤ | 5.0 | %, voltage droop bandwidth — mode 1 only |
| Q_Ramp_Rate_fast | ⑤ | — | kVAr/s fast ramp (ISCE Test 6) — bypassed in mode 3 |
| Q_Ramp_Rate_slow | ⑤ | — | kVAr/s slow ramp (ISCE Test 6) |
| Q_Ramp_Fast_Sel | ⑤ | FALSE | FALSE=slow, TRUE=fast |
| U_nom_kV | ⑤ | 110.0 | kV, POC nominal voltage — U_pu = U_meas / U_nom_kV (SMA envelope) |
| U_Kp | ⑤ | 2000.0 | kVAr/kV, PID proportional gain (mode 3) |
| U_Ki | ⑤ | 100.0 | kVAr/(kV·s), PID integral gain — Ti = 20 s (mode 3) |
| U_Kd | ⑤ | 0.0 | kVAr·s/kV, PID derivative gain — 0 = disabled (mode 3) |
| U_Kd_Tfilt | ⑤ | 0.5 | s, first-order low-pass filter time constant for derivative term |
| U_deadband_kV | ⑤ | 0.3 | kV, symmetric voltage deadband around setpoint (mode 3) |
| U_Tt | ⑤ | 20.0 | s, anti-windup tracking time constant (= Ti for PI) |
| PID_Reset | ⑤ | — | Write TRUE to reset integrator; FB_PPC_Controller auto-clears same cycle |

### UDT — Inverter_controller

| Field | Direction | Type | Description |
|---|---|---|---|
| Enabled | Config (operator) | Bool | Manual enable — NEVER overwritten by automatic logic |
| RemReady | Feedback | Bool | Inverter remote-ready state |
| Error | Feedback | Bool | Active inverter fault |
| CommError | Comms block | Bool | Modbus link broken |
| Available | Computed (step ①) | Bool | 6-condition online check — single source for all downstream FCs |
| WAval | Feedback | DInt | Available active power (pu × 10000, FIX4) |
| VArAval | Feedback | DInt | Available reactive power (pu × 10000, FIX4) |
| WSpt | Write | DInt | Active power setpoint (kW direct, FIX0) |
| VArSpt | Write | DInt | Reactive setpoint (kVAr direct, FIX0) |
| PFSpt | Write | DInt | Power factor setpoint (PF × 10000, FIX4) |
| OperMode | Write | DInt | InvOpMod: 308=Operation, 303=Stop |
| WMode | Write | DInt | GriMng.WMod: 1079=WCtlCom, 303=Off |
| VArMode | Write | DInt | GriMng.VArMod: 1072=VArCtlCom, 1075=PFCtlCom, 303=Off |
| ErrClr | Write | DInt | Fault acknowledge: 26=Ackn (one-shot), 0=idle |
| PwrOffReas | Feedback | DInt | Inverter disconnect reason code |
| DrtStt | Feedback | DInt | Derating state |

---

## 3. Plant Operating Modes

| Mode | Value | Behaviour |
|---|---|---|
| LOCAL | 0 | Operator controls targets from HMI. Frequency droop still active. |
| REMOTE_IEC | 1 | Targets from upstream SCADA/grid operator. Full PPC active. |
| FALLBACK | 2 | Comms lost (watchdog expired). P and Q ramp to zero; all inverters stopped. |

**Mode transitions:** LOCAL override has highest priority. FALLBACK activates when watchdog expires. Recovery from FALLBACK to REMOTE_IEC is automatic when comms restore — no manual reset required.

**On FALLBACK → REMOTE_IEC:** Both `Ramps_Pcmd` and `QCap_IDB.Ramps_Qcmd` are reset to 0 so ramp-up restarts cleanly from zero.

---

## 4. FC/FB Descriptions

---

### ① FC_PPC_InverterMonitor

**Purpose:** Scans all 10 inverters. Computes `Available` — the 6-condition online flag that is the single source of truth for all downstream FCs.

**6 online conditions (all must be TRUE):**
1. `Enabled = TRUE` — operator enabled in PPC configuration
2. `RemReady = TRUE` — inverter feedback confirms remote-ready state
3. `Error = FALSE` — no active fault (ErrStt = Ok)
4. `CommError = FALSE` — Modbus communication healthy
5. `PwrOffReas = 0` — no abnormal disconnect
6. `SKID_ELECTRIC.Skids[i].ELECTRIC_OK = TRUE` — all switchgear in deliverable state

```scl
FOR i := 0 TO 9 DO
    Inverters[i].Available :=
           Inverters[i].Enabled
       AND Inverters[i].RemReady
       AND NOT Inverters[i].Error
       AND NOT Inverters[i].CommError
       AND (Inverters[i].PwrOffReas = 0)
       AND SkidElectric[i].ELECTRIC_OK;
    IF Inverters[i].Available THEN
        N_Online  += 1;
        PmaxPlant += DINT_TO_REAL(WAval[i])   / 10000.0 × WRtg_kW;   // pu → kW
        QmaxPlant += DINT_TO_REAL(VArAval[i]) / 10000.0 × WRtg_kW;   // pu → kVAr
    END_IF;
END_FOR;
```

**Why raw DInt for ratios downstream:** In distribution FCs, only the ratio `WAval_i / ΣWAval_j` is needed — the ÷10000 and WRtg factors cancel. Raw DInt values are used directly. Conversion is required only here (absolute kW for PmaxPlant/QmaxPlant).

---

### ② FC_PPC_ModeManager

**Purpose:** Determines Plant_Mode from watchdog status and HMI override. No timer logic — the TON timer lives in FB_PPC_Controller static.

**Priority order:**
1. `LocalMode_Req = TRUE` → Plant_Mode = 0 (LOCAL), return
2. `WD_Expired = TRUE` → Plant_Mode = 2 (FALLBACK), return
3. Otherwise → Plant_Mode = 1 (REMOTE_IEC)

Priority 3 also handles FALLBACK recovery: once comms restore, `WD_Expired` goes FALSE and mode returns to REMOTE_IEC on the very next scan.

---

### ③ FC_PPC_RampControl

**Purpose:** Limits rate of change of the AGC `Cmd_P` input only. Produces `Ramps_Pcmd`.

**Does NOT limit frequency droop response.** Droop is applied in step ④ after this FC — frequency events are immediate.

```
effectiveTarget := 0.0 if Plant_Mode = 2, else Cmd_P

delta := effectiveTarget − Ramps_Pcmd
IF delta > 0: Ramps_Pcmd += MIN(delta, P_RampUp × CycleTime_s)
ELSIF delta < 0: Ramps_Pcmd −= MIN(|delta|, P_RampDown × CycleTime_s)

Ramps_Pcmd := MIN(Ramps_Pcmd, PmaxPlant)   // cap to available capacity
Ramps_Pcmd := MAX(Ramps_Pcmd, 0.0)          // PV cannot produce negative power
```

---

### ④ FB_PPC_FreqResponse — ANRE Ordinul 51/2019

**Purpose:** Primary frequency response (RFA — Reglaj Frecventa-Activitate). Adds droop correction to `Ramps_Pcmd` without rate limiting. Output `P_final_kW` feeds step ⑥.

**State retained between OB30 cycles:** `Trip_Latch : Bool`, `Reconnect_TON : TON`, `Reconnect_LastEnable : Bool`.

#### Frequency source selection

`Frequency_Source_Sel = FALSE` → use `f_meas` (grid AI, normal operation).
`Frequency_Source_Sel = TRUE` → use `Freq_Test_Override` (ISCE 4–20 mA test bench, 47.5–52.0 Hz range).
Both SCADA-writable for switching during ISCE campaign without code change.

#### Droop formula (Art. 114–115 OF / Art. 118–120 UF)

ANRE specifies different droop values for each direction — over-frequency uses `Droop_OF_pct` (8%),
under-frequency uses `Droop_UF_pct` (10%):

```
df       = f_active − f_nom
Pn_kW    = Pn_MW × 1000

IF |df| ≤ DeadBand_mHz / 1000:
    dP_droop = 0                                        // inside dead band — hard cutout
ELSIF df > 0:                                           // over-frequency (Art. 114-115)
    dP_droop = −(2 × Pn_kW × df) / Droop_OF_pct       // reduces P
ELSE:                                                   // under-frequency (Art. 118-120)
    dP_droop = −(2 × Pn_kW × df) / Droop_UF_pct       // increases P

P_cmd_raw  = Ramps_Pcmd + dP_droop
P_final_kW = LIMIT(0, P_cmd_raw, Pmax_active)           // Pmin lower clamp: diagnostic only
```

Sign convention: df > 0 (over-frequency) → dP_droop < 0 (reduce active power). df < 0 (under-frequency) → dP_droop > 0 (increase active power).

#### Dynamic Pmin/Pmax band (Note 1, ISCE test program)

Each direction reserves its own 200 mHz headroom using its own droop value:

```
dP_at_200mHz_OF = (2 × Pn_kW × 0.200) / Droop_OF_pct  → 2300 kW at 8% (46 MW plant)
dP_at_200mHz_UF = (2 × Pn_kW × 0.200) / Droop_UF_pct  → 1840 kW at 10%

Pmax_active = Pmax_disp  − dP_at_200mHz_OF    // OF headroom: caps ramp output
Pmin_active = Pmin_stab  + dP_at_200mHz_UF    // UF headroom: diagnostic only
```

Ensures the plant can deliver the full ±200 mHz droop response without saturation. Recomputed every cycle — tracks irradiance changes via PmaxPlant and droop setting changes.

#### Dead band (Art. 117)

Hard cutout: `|df| ≤ DeadBand_mHz / 1000 Hz` → no response. **Not a soft blend.**
Set `DeadBand_mHz = 0` via SCADA for Art.117 fine-response sub-test — verifies response exists right up to df = 0.

#### Trip and reconnect (Art. 118–120, 126–131)

`Trip_FreqFault` latches TRUE when:
- `f_active > OFRT_Trip_Hz` (51.5 Hz) — over-frequency
- `f_active < UFRT_Trip_Hz` (47.5 Hz) — under-frequency

When tripped:
- `P_final_kW = 0` immediately (bypasses ramp)
- **No physical breaker is tripped** — only inverter setpoints are zeroed
- Caller (`FB_PPC_Controller` step ④) also resets `Ramps_Pcmd := 0` so reconnect ramp-up starts from zero

Trip clears: `Reconnect_Enable` rising edge AND f back in normal band.

`Reconnect_Timer_s`: measures elapsed time from trip-clear to P reaching 95% of `Pmax_active`. Required for ISCE Test 7 reconnect timing measurement.

#### Validation tests (ISCE test programme)

| Test | Article | Droop | Description |
|---|---|---|---|
| Test 1 | 114–115 | 8%, 10% | Over-frequency: 50→50.2→50.5→51→51.5→back |
| Test 2 | 118–120 | 8%, 10% | Under-frequency: 50→49.8→49.5→49→48.5→48→back |
| Test 3 | 117 | 8%, 10% | Fine response: 200 mHz + 50 mHz steps; 50 mHz sub-test with DeadBand=0 |
| Test 4 | 118–120 | 10% | Full sweep + trip at >51.5 Hz + reconnect sequence |
| Test 7 | 126–131 | — | Reconnect timing: Reconnect_Timer_s measured |

---

### ⑤ FB_PPC_QCapability — ANRE Ordinul 51/2019

**Purpose:** Generates plant-level Q command through three sequential stages:
1. Control mode → raw Q command (fixed-Q, U-droop, or U-Control PID)
2. Q ramp rate limiting (bypassed in mode 3 — PID's Ki already limits rate)
3. P-Q capability envelope clamp (also used as saturation limits for PID anti-windup)

Output `Q_final_kVAr` feeds step ⑦.

**State retained between OB30 cycles:** `Ramps_Qcmd : Real` (Q ramp accumulator, moved here from FB_PPC_Controller), `PQ_Table : Array[0..4] of UDT_PQ_CapPoint` (capability table, configured from HMI via instance DB).

#### Q ramp relocation

The Q ramp accumulator was previously `Ramps_Qcmd` in FB_PPC_Controller static. It now lives in `QCap_IDB.Ramps_Qcmd` (this FB's instance DB). FC_PPC_ReactiveControl no longer performs any Q ramping. Resets:
- `QCap_IDB.Ramps_Qcmd := 0.0` in EN_PPC=FALSE guard
- `QCap_IDB.Ramps_Qcmd := 0.0` on FALLBACK → REMOTE_IEC transition
- Resets via FaultHandler VAR_IN_OUT when `onlineCount = 0`

#### P-Q capability table (Art. 147, 152 — ISCE Test 8)

`PQ_Table[0..4]` of `UDT_PQ_CapPoint` in the FB instance DB. Configure from HMI/SCADA before ISCE Test 8.

| Index | P_pct (configure) | Q_ind_max (kVAr) | Q_cap_max (kVAr) |
|---|---|---|---|
| 0 | 0 | [enter] | [enter] |
| 1 | 25 | [enter] | [enter] |
| 2 | 50 | [enter] | [enter] |
| 3 | 75 | [enter] | [enter] |
| 4 | 100 | [enter] | [enter] |

Default: 20 000 kVAr at all tiers (non-limiting until commissioned — replace with plant-specific values from inverter datasheets and ANRE Category D requirements).

Runtime Q limits computed by linear interpolation at `P_actual_kW / Pmax_kW`:
```
P_pct   = P_actual_kW / Pmax_kW × 100
tbl_idx = FLOOR(P_pct / 25)         // lower bracket index (0..3)
t0      = (P_pct − tbl_idx × 25) / 25    // fractional position [0, 1)
Q_ind_interp = PQ_Table[tbl_idx].Q_ind_max + t0 × (PQ_Table[tbl_idx+1].Q_ind_max − prev)
Q_cap_interp = PQ_Table[tbl_idx].Q_cap_max + t0 × (PQ_Table[tbl_idx+1].Q_cap_max − prev)
```

#### Control modes (VArControl_Mode — separate from Plant_VArMode in ReactiveControl)

**Mode 0 — Fixed Q:**
`Q_command = Q_setpoint_ext` (from SCADA). Ramp applied. P-Q clamped.

**Mode 1 — Voltage droop (Art. 160, 163 — ISCE Test 9):**
```
dU_pu     = (U_setpoint_ext − U_meas) / U_meas       // fractional per-unit error
Q_command = (dU_pu / (U_Droop_pct / 100)) × QmaxPlant
```
Gain is adaptive — scales with actual available Q capacity (`QmaxPlant` from step ①). Ramp applied. P-Q clamped.

**Mode 2 — Off:** `Q_command = 0`. Used when `Plant_VArMode = 2` (PF mode in ReactiveControl).

**Mode 3 — U Control PID (closed-loop voltage regulation):**

PI(D) controller that drives `U_meas` toward `U_setpoint_ext` by adjusting reactive output. Starting values derived from grid SSC = 700 MVA at 110 kV (SCR ≈ 15).

```
Sign convention: positive Q = inductive (absorbs VARs → decreases voltage)
                 negative Q = capacitive (injects VARs → increases voltage)

U_err    = U_meas − U_setpoint_ext           // positive → over-voltage → need +Q (inductive)
           zeroed if |U_err| < U_deadband_kV

Q_unsat  = U_Kp × U_err + I_term + D_term

// Anti-windup: back-calculation tracks Q capability limits each scan
I(k+1) = I(k) + U_Ki × U_err × dt + (dt/U_Tt) × (Q_sat − Q_unsat)

// Derivative on measurement (avoids setpoint-step kick), IIR-filtered:
D_filt(k+1) = D_filt(k) + (dt/U_Kd_Tfilt) × (−dU_meas/dt − D_filt(k))
D_term      = U_Kd × D_filt
```

**Saturation:** Q_unsat clamped to `[−Q_ind_interp, +Q_cap_interp]` (Stage 1 P-Q capability limits, computed dynamically each scan).

**Bumpless transfer into mode 3:** `I_init = Ramps_Qcmd − U_Kp × (U_meas − U_setpoint_ext)` — output continuity on mode switch.

**Ramp bypass:** In mode 3 `Ramps_Qcmd := Q_command` (tracks PID output for bumpless handover when switching back to modes 0/1).

**PID reset conditions:** integrator cleared when Plant_Mode = FALLBACK, N_Online = 0, or SCADA writes `PID_Reset = TRUE`.

#### Q ramp logic (ISCE Test 6)

Two independently-selectable rates: `Q_Ramp_Rate_fast` / `Q_Ramp_Rate_slow`. Selected via `Q_Ramp_Fast_Sel`. Same logic as FC_PPC_RampControl. In FALLBACK: effective target forced to 0 — Q descends gracefully.

```
Q_ramp_rate := fast or slow per selector
IF Plant_Mode = 2: effectiveTarget = 0, else = Q_command
delta = effectiveTarget − Ramps_Qcmd
IF delta > 0: Ramps_Qcmd += MIN(delta, Q_ramp_rate × CycleTime_s)
ELSIF delta < 0: Ramps_Qcmd −= MIN(|delta|, Q_ramp_rate × CycleTime_s)
```

#### Stage 1 — ANRE P-Q capability clamp and Q_limited flag

```
IF Ramps_Qcmd > Q_cap_interp:  Q_setpoint_final = Q_cap_interp
ELSIF Ramps_Qcmd < −Q_ind_interp: Q_setpoint_final = −Q_ind_interp
ELSE: Q_setpoint_final = Ramps_Qcmd

Q_limited = (Ramps_Qcmd clamped by ANRE P-Q envelope)    // diagnostic
```

Also clamps to `QmaxPlant` (belt-and-suspenders: physical inverter capacity).

#### Stage 2 — SMA physical envelope clamp

A second, independent clamp enforces the **SMA SC 4600 UP hardware limit** — the maximum Q the
inverter can physically deliver at the current P and grid voltage. This is separate from the ANRE
regulatory table because exceeding it would overload the inverter (S > Smax = 4600 kVA).

```
P_per_inv   = P_setpoint_kW / N_Online           // per-inverter P (from FreqResponse output)
FC_SMA_QEnvelope(P_kW := P_per_inv, U_pu := U_pu)  → Qmax_inv_kVar
SMA_Q_limit = Qmax_inv_kVar × N_Online

IF Q_setpoint_final > +SMA_Q_limit:  Q_setpoint_final = +SMA_Q_limit; Q_SMA_limited = TRUE
IF Q_setpoint_final < −SMA_Q_limit:  Q_setpoint_final = −SMA_Q_limit; Q_SMA_limited = TRUE
```

**Key design decisions:**
- Uses `P_setpoint_kW` (FreqResponse output = what inverters are actually commanded) — NOT
  `P_actual_kW` (grid meter, lags during ramps and is unreliable/zero in simulation)
- `U_pu = U_meas / U_nom_kV` (110 kV nominal); division-by-zero guarded to 1.0
- `SMA_Qmax_plant` and `Q_SMA_limited` mirrored to DB39 for SCADA/ISCE monitoring

**Example at full P load (46 MW, U=1.0 pu):**
- FreqResponse reserves 2300 kW headroom → P_setpoint = 43700 kW → P_per_inv = 4370 kW
- FC_SMA_QEnvelope at P=4370 kW → Qmax_inv = 1436 kVAr
- SMA_Q_limit = 1436 × 10 = 14360 kVAr → plant S = √(43700² + 14360²) ≈ 45826 kVA < 46000 ✓

#### Zero-P reactive capability (Art. 150, 152 — ISCE Test 10)

Q dispatch is not gated on P > 0. Inverters with `OperMode = 308` (maintained by FaultHandler for all healthy inverters) can source/sink Q even when `WSpt = 0`. No P > 0 guard exists in this FB, in FC_PPC_ReactiveControl, or in FC_PPC_FaultHandler.

---

### ⑥ FC_PPC_PowerDistribution

**Purpose:** Splits `P_final_kW` (droop-corrected, from step ④) across all available inverters proportionally by WAval. Writes `WSpt` and `WMode`.

Receives `P_final_kW` where the old code passed `Ramps_Pcmd`. Internal logic unchanged — proportional distribution, per-inverter WSpt clamp.

Returns immediately in FALLBACK — FaultHandler owns the safe-state writes.

```
sumWAval_raw := 0
FOR i = 0 TO 9: IF Available[i] THEN sumWAval_raw += WAval[i]

FOR i = 0 TO 9:
    IF Available[i] AND sumWAval_raw > 0:
        share   = WAval[i] / sumWAval_raw                          // dimensionless ratio
        WSpt[i] = REAL_TO_DINT(P_final_kW × share)                // kW FIX0
        maxWSpt = WAval[i] / 10000 × WRtg_kW → clamp WSpt[i]     // per-inverter ceiling
        WMode[i] = 1079  (WCtlCom)
    ELSE:
        WSpt[i] = 0;  WMode[i] = 303  (Off)
```

---

### ⑦ FC_PPC_ReactiveControl

**Purpose:** Distributes `Q_final_kVAr` (from step ⑤ — already ramped and P-Q clamped) across all available inverters by VArAval. For PF mode, writes uniform PF setpoint.

**Q ramp has been removed from this FC.** It is now owned entirely by FB_PPC_QCapability (step ⑤). ReactiveControl receives an already-ramped, capability-clamped command and only performs per-inverter distribution.

**Modes (Plant_VArMode — from FB_PPC_Controller input Cmd_VArMode):**

| Mode | Action |
|---|---|
| 0 = Off | VArSpt = 0, VArMode = 303 for all available inverters |
| 1 = Q control | Distribute Q_final_kVAr proportionally by VArAval; VArMode = 1072 |
| 2 = PF uniform | Real mode: PFSpt = Targets_PF × 10000, VArMode = 1075. Sim mode: see below |

Mode 1 covers both fixed-Q and U-droop sub-modes — the Q source distinction is resolved upstream in QCapability (VArControl_Mode).

**Mode 2 — PF simulation behaviour (`Sim_Mode = TRUE`):**
Real SMA inverters execute PF control autonomously from their PFSpt register. In simulation no real
inverter hardware is present, so PF mode would produce zero visible Q. Instead, the FC computes
equivalent Q per inverter from P and the PF target, then clamps to the SMA physical envelope:

```
Q_sim = WSpt_i × sqrt(1 − PF²) / |PF| × sign(PF)
FC_SMA_QEnvelope(P_kW := WSpt_i, U_pu := U_pu) → Qmax_inv
Q_sim = LIMIT(−Qmax_inv, Q_sim, +Qmax_inv)
VArSpt_i = REAL_TO_DINT(Q_sim);  VArMode = 1072   // VArCtlCom in sim
```

**PFSpt = 0 guard:** SMA inverters reject PFSpt = 0. If `Targets_PF = 0` or not yet set, the FC
writes `PFSpt = 10000` (unity PF) as a safe default and issues VArMode = 1075.

Returns immediately in FALLBACK — FaultHandler owns safe-state writes.

---

### ⑧ FC_PPC_FaultHandler

**Purpose:** Runs last. Overrides setpoints written by steps ⑥/⑦ for faulted / stopped / disconnected inverters. Writes `OperMode` to keep healthy inverters in Operation.

**Per-inverter logic (five cases, strict priority):**

| Priority | Condition | Action |
|---|---|---|
| A | `ForceStop OR Plant_Mode = 2` | Stop ALL: OperMode=303, WSpt=0, VArSpt=0, WMode=303, VArMode=303, ErrClr=0 |
| B | `CommError = TRUE` | Same stop writes; AnyFault=TRUE; FaultMask bit set |
| C | `Error = TRUE` | Zero WSpt/VArSpt/PFSpt/ErrClr; AnyFault=TRUE; FaultMask bit set; OperMode not written |
| D | Healthy, `PwrOffReas ≠ 0 OR NOT ELECTRIC_OK` | OperMode=308; zero setpoints; AnyFault=TRUE (belt-and-suspenders vs InverterMonitor.Available) |
| E | Fully healthy | OperMode=308; ErrClr one-shot on Error↓ edge; DrtStt≠0 → AnyDerating=TRUE |

**ErrClr one-shot (sequence S3.3):** Write 26 (Ackn) for exactly one scan when Error transitions 1→0 (fault cleared). Also re-sent when `Enabled` rises while Error is clear (M6 fix: handles case where one-shot fired while disabled).

**Ramps reset:** When `onlineCount = 0`, both `Ramps_Pcmd` and `QCap_IDB.Ramps_Qcmd` are reset to 0.0 via VAR_IN_OUT pass-through. Ensures clean ramp-up from zero when inverters recover.

---

## 5. FB_PPC_Controller

**Purpose:** Main orchestrator. Holds timer state, detects watchdog edge, instantiates multi-instance FBs, calls all eight steps, mirrors results to DB39.

### Interface

**Inputs (set by OB30 caller):**

| Variable | Type | Description |
|---|---|---|
| EN_PPC | Bool | Master enable. FALSE → immediate safe state |
| IEC_Watchdog | Bool | Heartbeat toggle from upstream comms thread |
| CycleTime_s | Real | OB30 cycle time in seconds (0.1 for 100 ms) |
| Cmd_P | Real | kW, active power target from upstream |
| Cmd_Q | Real | kVAr, reactive power target from upstream |
| Cmd_PF | Real | Power factor target (e.g. 0.95) |
| Cmd_VArMode | Int | Reactive mode: 0=Off / 1=Q dispatch / 2=PF |
| LocalMode_Req | Bool | HMI LOCAL override |
| **f_meas** | **Real** | **Hz, grid-measured frequency (AI)** |
| **Freq_Test_Override** | **Real** | **Hz, ISCE test bench frequency (AI, 47.5–52.0 Hz)** |
| **Frequency_Source_Sel** | **Bool** | **FALSE=real, TRUE=test bench (SCADA-writable)** |
| **U_meas** | **Real** | **kV, MV busbar measured voltage (AI)** |
| **P_actual_kW** | **Real** | **kW, plant actual power from grid meter (AI)** |

**Outputs:**

| Variable | Type | Description |
|---|---|---|
| PPC_Active | Bool | TRUE when Plant_Mode = 1 (REMOTE_IEC) |
| PPC_Fault | Bool | Any fault active |
| AnyDerating | Bool | Any derating active |
| Mode_Out | Int | Current Plant_Mode (0/1/2) |

**Static variables (retained between OB30 cycles):**

| Variable | Type | Description |
|---|---|---|
| Watchdog_TON | TON | Timer since last watchdog edge |
| Watchdog_LastBit | Bool | Previous IEC_Watchdog for edge detection |
| Watchdog_Timeout | Time | Default T#30S |
| Plant_Mode | Int | Current mode |
| Ramps_Pcmd | Real | Ramped P command accumulator |
| PrevMode | Int | For FALLBACK→REMOTE_IEC detection (S4 fix) |
| PrevError_Arr | Array[0..9] of Bool | For ErrClr one-shot edge detection (S3.3) |
| PrevEnabled_Arr | Array[0..9] of Bool | For ErrClr re-send on re-enable (M6) |
| **FreqResp_IDB** | **FB_PPC_FreqResponse** | **Multi-instance: step ④** |
| **QCap_IDB** | **FB_PPC_QCapability** | **Multi-instance: step ⑤** |

> **Note:** `Ramps_Qcmd` is no longer a static variable here — it lives in `QCap_IDB.Ramps_Qcmd`. Reset it via `QCap_IDB.Ramps_Qcmd := 0.0` when needed.

### Watchdog Logic

```
WD_EdgeDetected := IEC_Watchdog AND NOT Watchdog_LastBit
Watchdog_LastBit := IEC_Watchdog

IF WD_EdgeDetected:  call TON(IN=FALSE)   // reset timer
ELSE:                call TON(IN=TRUE)    // count up

WD_Expired := TON.Q   // TRUE if no toggle for > Watchdog_Timeout
```

### EN_PPC = FALSE Guard

When EN_PPC is FALSE: calls FaultHandler with ForceStop=TRUE, resets `Ramps_Pcmd := 0`, `QCap_IDB.Ramps_Qcmd := 0`, `FreqResp_IDB.Trip_Latch := FALSE`, sets Plant_Mode=0, writes outputs, and returns immediately.

### Frequency Trip Reset

After calling FreqResp_IDB (step ④):
```scl
IF FreqResp_IDB.Trip_FreqFault THEN
    Ramps_Pcmd := 0.0;   // reset P ramp so reconnect starts from zero
END_IF;
```

### FALLBACK → REMOTE_IEC Recovery (S4 fix)

```scl
IF (PrevMode = 2) AND (Plant_Mode ≠ 2) THEN
    Ramps_Pcmd           := 0.0;
    QCap_IDB.Ramps_Qcmd := 0.0;
END_IF;
PrevMode := Plant_Mode;
```

### DB39 Mirror Writes

| After step | Values mirrored to DB39 |
|---|---|
| ① | Plant_N_Online, Limits_PmaxPlant, Limits_QmaxPlant |
| ② | Plant_Mode |
| ③ | Ramps_Pcmd |
| ④ | dP_droop, FreqResp_Pmin, FreqResp_Pmax, Trip_FreqFault, Reconnecting, Reconnect_Timer_s |
| ⑤ | Q_max_inductive, Q_max_capacitive, Q_limited, Ramps_Qcmd (mirror of QCap_IDB.Ramps_Qcmd), SMA_Qmax_plant, Q_SMA_limited, U_error_kV, PID_I_term, PID_saturated, PID_active |
| ⑧ | AnyFault, AnyDerating, FaultMask |

---

## 6. Comms Layer Separation

PPC FCs/FBs write only to UDT fields in `PPC_Inverters` (`WSpt`, `WMode`, `OperMode`, etc.). A separate Modbus comms block maps UDT fields → holding register writes (FC16) each cycle. Feedback values are read from inverter input registers (FC04) and written into the UDT by the same comms block.

This means PPC logic is completely register-address agnostic. The comms block can be updated without touching any PPC FC.

---

## 7. SKID_ELECTRIC Switchgear Interlock

`ELECTRIC_OK` for each skid is derived from 7 hardwired DI signals per skid (separator, earthing switch, breaker in 3 switchgear cells) by `FC_SkidElectricStatus`. Called 10× in OB30 **before** FB_PPC_Controller.

ELECTRIC_OK is the **6th condition** in `Inverters[i].Available` (step ①). If FALSE:
- Inverter excluded from N_Online, PmaxPlant, QmaxPlant
- WSpt/VArSpt/PFSpt zeroed by FaultHandler (belt-and-suspenders)
- AnyFault = TRUE
- OperMode = 308 maintained (instant recovery when switchgear restored)

`Inverter.Enabled` is never overwritten by the ELECTRIC_OK logic — it remains exclusively operator/HMI controlled.

---

## 8. Implementation Checklist for TIA Portal

| # | Item | Status |
|---|---|---|
| 1 | Import `UDT_PQ_CapPoint`, `Skid_Electric_Status`, `Inverter_controller` | Done |
| 2 | Import all SCL files as program blocks | Done |
| 3 | Create `SKID_ELECTRIC` DB: `Skids: Array[0..9] of Skid_Electric_Status` | TIA Portal only |
| 4 | Add new DB39 fields: f_nom, Pn_MW, **Droop_OF_pct** (8.0), **Droop_UF_pct** (10.0), DeadBand_mHz, Pmin_stab, OFRT/UFRT_Trip_Hz, Reconnect_Enable, VArControl_Mode, **U_nom_kV** (110.0), U_setpoint_ext, U_Droop_pct, Q_Ramp_Rate_fast/slow, Q_Ramp_Fast_Sel, U_Kp (2000.0), U_Ki (100.0), U_Kd (0.0), U_Kd_Tfilt (0.5), U_deadband_kV (0.3), U_Tt (20.0), PID_Reset, and diagnostics (SMA_Qmax_plant, Q_SMA_limited, U_error_kV, PID_I_term, PID_saturated, PID_active) | TIA Portal only |
| 4a | Import new objects: UDT_SMA_QRow, UDT_SMA_QTable, DB_SMA_SC4600UP (constant DB), FC_SMA_QEnvelope | TIA Portal only |
| 5 | Configure PQ_Table in QCap instance DB (5 tiers × kVAr values) | Before ISCE Test 8 |
| 6 | Wire 5 new FB_PPC_Controller inputs in OB30 call (f_meas, Freq_Test_Override, Frequency_Source_Sel, U_meas, P_actual_kW) | Commissioning |
| 7 | Configure AI blocks: f_meas (4–20 mA → 47.5–52.0 Hz), P_actual (4–20 mA → kW), U_meas | Commissioning |
| 8 | Wire hardwired DI signals into SKID_ELECTRIC.Skids[i].* fields | Commissioning |
| 9 | Verify switchgear contact polarity (TRUE = closed assumed) | Before energising |
| 10 | Set Pn_MW = 46.0, **Droop_OF_pct = 8.0, Droop_UF_pct = 10.0**, DeadBand_mHz = 200.0, OFRT_Trip_Hz = 51.5, UFRT_Trip_Hz = 47.5, **U_nom_kV = 110.0** in DB39 (FC_PPC_InitData does this automatically) | Before ISCE campaign |
| 11 | ISCE test sequence: Test 1→2→3→4, then 6→7, then 8→9→10, then 12 | ISCE campaign |

---

*Document version: 2026-07-15 | Updated: Added VArControl_Mode 3 (U Control PID) in FB_PPC_QCapability — PI(D) closed-loop voltage regulator with back-calculation anti-windup, derivative-on-measurement (IIR filtered), symmetric deadband, bumpless transfer, ramp bypass. PID params (U_Kp=2000, U_Ki=100, U_Kd=0, U_Kd_Tfilt=0.5, U_deadband_kV=0.3, U_Tt=20, PID_Reset) moved to PPC_Controller DB for flat SCADA access. PID diagnostics (U_error_kV, PID_I_term, PID_saturated, PID_active) mirrored to DB39. Sign convention: positive Q = inductive. Starting values from SSC=700 MVA at 110 kV. Previous: Split Droop_pct → Droop_OF_pct (8%, Art.114-115) + Droop_UF_pct (10%, Art.118-120); Stage 2 SMA physical envelope clamp; Sim_Mode PF→Q. | Source: ANRE Ordinul 51/2019, Ordinul 60/2024; ISCE Program de Probe CEF Tandarei 2026*
