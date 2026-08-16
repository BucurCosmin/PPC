# SMA Sunny Central — Modbus Comms Block Mapping

**Target:** PPC_Controller [DB39], UDT `Inverter_controller`  
**Connection:** Modbus TCP — **Unit ID 2** (fast setpoints, cyclic 100 ms) + **Unit ID 3** (measurements, parameters, event-driven writes)  
**Source (current):** `SMA\MODBUS-SC-TI-en-20.pdf` (v2.0, firmware ≥ 10.03.xx.R — installed: 10.03.14.R)  
**Source (previous):** `SMA\MODBUS-SCxxxx-TI-en-19.pdf` (v1.9 — deprecated registers kept in §2.4 and §4.2 for transition reference)

> **v2.0 key change:** Fast setpoints (WSpt, VArSpt, PF) moved from Unit ID 3 kW/kVAr registers to Unit ID 2 % FIX2 registers. Mode/config parameters (InvOpMod, RemRdy, VArMod, WMod) remain on Unit ID 3 but must be **event-driven** — not cyclic. Same TCP socket handles both Unit IDs.

---

## 1. Conventions

| Item | Value |
|---|---|
| Modbus protocol | TCP/IP |
| Unit ID 2 | Fast setpoints — WSpt %, VArSpt %, PF (cyclic 100 ms) |
| Unit ID 3 | Measurements, status, parameters (reads cyclic; mode writes event-driven) |
| TCP socket | **Single connection** — Unit ID switched per FSM state |
| Register bit-width (UID3) | 32-bit values — each occupies **2 consecutive 16-bit registers** |
| Register bit-width (UID2) | 16-bit values (S16/U16) — each occupies **1 register** |
| Addressing | 0-based (register 0 = first holding or first input register) |
| Write function code | **FC16** (0x10) Write Multiple Holding Registers |
| Read holding registers | **FC03** (0x03) Read Holding Registers |
| Read input registers | **FC04** (0x04) Read Input Registers |
| Endianness | Big-endian (Motorola), high word first |
| Cycle | 100 ms (OB30) — read first, then compute, then write |

**Scaling formats:**

| Format | Scaling | Example |
|---|---|---|
| ENUM | 1 (integer code) | InvOpMod: 308 = Operation |
| FIX0 | ×1 — value in physical units | WSpt (v1.9): 500 → 500 kW |
| FIX1 | ×10 | GriMs.Hz: 5000 → 50.00 Hz |
| FIX2 | ×100 | WSpt (v2.0): 10000 → 100.00%, −5000 → −50.00% |
| FIX4 | ×10000 | PFSpt: 9500 → PF 0.9500 |

**Register address note:** WSpt, VArSpt, and PFSpt appear in the SMA register map as *Input Register* readbacks (FC04, read-only). SMA Sunny Central also accepts FC16 writes to these same addresses when the corresponding control mode (WCtlCom / VArCtlCom / PFCtlCom) is active. The FC04 readback confirms what setpoint the inverter is currently tracking.

---

## 2. WRITE to SMA Inverter — FC16 (PLC → Inverter)

### 2.1 v2.0 Cyclic Writes — Unit ID 2, FC16 (fast setpoints, every 100 ms)

| # | Skid UDT Field | SMA Channel | PDU Addr | Words | Data Type | Format | Unit | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | `VArSpt_pct` | `VArSpt` | **22** | 1 | S16 | FIX2 % | % of VArRtg | −100% to +100% |
| 2 | `WSpt_pct` | `WSpt` | **23** | 1 | S16 | FIX2 % | % of WRtg | −100% to +100% |
| 3 | `PF_cos` | *(PF magnitude)* | **24** | 1 | U16 | FIX4 | — | cos_phi × 10000 |
| 4 | `PF_excitation` | *(PF direction)* | **25** | 2 | U32 | ENUM | — | Over/underexcited |

VArSpt_pct and WSpt_pct are adjacent → written in **one FC16 frame** (addr=22, len=2, FSM State 4).  
PF registers (addr=24, len=3) are a separate FC16 frame (FSM State 5), written **only when PF mode is active**.

**Scaling formula — SC 4600 UP (hardcoded reference values):**

```scl
// WExlSpt.RefVal = 4600 kW (UID3 addr 269), VArExlSpt.RefVal = 2760 kVAr (UID3 addr 268)
// Hardcoded — read from inverter only if dynamic derating is later required
WSpt_raw   := REAL_TO_INT(DINT_TO_REAL(Inverter.WSpt)   / 4600.0 * 10000.0);
VArSpt_raw := REAL_TO_INT(DINT_TO_REAL(Inverter.VArSpt) / 2760.0 * 10000.0);
// 100% = raw 10000 | −50% = raw −5000 | S16 range ±32767 covers ±327.67% safely
```

**Scaling examples:**

| PPC setpoint | Raw value | Physical meaning |
|---|---|---|
| WSpt = 4600 kW | 10000 | 100% rated power |
| WSpt = 2300 kW | 5000 | 50% rated power |
| VArSpt = −1380 kVAr | −5000 | −50% (capacitive) |
| VArSpt = 0 kVAr | 0 | No reactive power |

**PF excitation ENUM values (UID2 addr 25):**

| Code | Meaning |
|---|---|
| 1041 | Over-excited (inductive, lagging) |
| 1042 | Under-excited (capacitive, leading) |

### 2.2 v2.0 Event-Driven Writes — Unit ID 3, FC16 (parameters, on change only)

> ⚠️ **v2.0 rule:** Writing these registers every 100 ms cycle updates SMA non-volatile storage and is explicitly prohibited. Write **only when the value changes** using a change-detect latch in the FSM (State 6).

| # | UDT Field | SMA Channel | Reg Addr (DEC) | Words | Data Type | Format | Unit |
|---|---|---|---|---|---|---|---|
| 1 | `OperMode` | `InvOpMod` | **0** | 2 | S32 | ENUM | — |
| 2 | *(derived)* | `RemRdy` | **2** | 2 | S32 | ENUM | — |
| 3 | `VArMode` | `GriMng.VArMod` | **4** | 2 | S32 | ENUM | — |
| 4 | `WMode` | `GriMng.WMod` | **6** | 2 | S32 | ENUM | — |
| 5 | `ErrClr` | `ErrClr` | **8** | 2 | S32 | ENUM | — |

> RemRdy (reg 2) must be written **before** InvOpMod (reg 0). Both are packed into the same FC16 frame (addr=0, len=10) so sequencing is preserved.

### 2.3 ENUM Values for Write Registers

#### InvOpMod (Holding Reg 0) — Unique ID 329

| Code | Text | Meaning |
|---|---|---|
| **308** | Operation | Command inverter to operate / RUN |
| **303** | Stop | Command inverter to stop |

#### RemRdy (Holding Reg 2) — Unique ID 331

| Code | Text | Meaning |
|---|---|---|
| **308** | Ready | Allow inverter to operate |
| **303** | Standby | Place inverter in standby |

#### GriMng.WMod (Holding Reg 6) — Unique ID 6078

| Code | Text | Meaning |
|---|---|---|
| **1079** | WCtlCom | Active power limit via Modbus (PPC/SCADA) |
| 1077 | WCtlMan | Manual (local HMI) |
| 1390 | WCtlAnIn | Analog input |
| **303** | Off | No active power control |

#### GriMng.VArMod (Holding Reg 4) — Unique ID 6080

| Code | Text | Meaning |
|---|---|---|
| **1072** | VArCtlCom | Reactive power (kVAr) via Modbus |
| **1075** | PFCtlCom | Power factor via Modbus |
| 2270 | AutoCom | Automatic — PPC selects Q or PF |
| 1071 | VArCtlMan | Manual kVAr |
| 1074 | PFCtlMan | Manual PF |
| 1387 | VArCtlAnIn | Analog input kVAr |
| 1388 | PFCtlAnIn | Analog input PF |
| **303** | Off | No reactive control |

#### ErrClr (Holding Reg 8) — Unique ID 733

| Code | Text | Meaning |
|---|---|---|
| **26** | Ackn | Acknowledge present fault — **one-shot rising edge only** |
| 973 | — | No action (idle) |

### 2.4 v1.9 Write Registers — Unit ID 3 (DEPRECATED)

> ⚠️ **These are the v1.9 setpoint write registers.** Kept here for transition reference while both FSM paths coexist. Remove once UID2 v2.0 path is validated on hardware.

| # | UDT Field | SMA Channel | Reg Addr (DEC) | Words | Data Type | Format | Unit |
|---|---|---|---|---|---|---|---|
| 1 | `WSpt` | `WSpt` | **108** | 2 | S32 | FIX0 | kW |
| 2 | `VArSpt` | `VArSpt` | **112** | 2 | S32 | FIX0 | kVAr |
| 3 | `PFSpt` | `PFSpt` | **114** | 2 | S32 | FIX4 | — |

Scaling examples (v1.9):

| UDT Value | Register Value | Physical Value |
|---|---|---|
| WSpt = 2000 | 2000 | 2000 kW |
| VArSpt = −500 | −500 | −500 kVAr (capacitive) |
| PFSpt = 0.95 | 9500 | cos φ = 0.950 (lagging) |
| PFSpt = 1.00 | 10000 | cos φ = 1.000 (unity) |

### 2.5 Critical Write Sequencing — SMA Interlock Rules

**START sequence (OperMode → 308):**
1. Write `RemRdy = 308` (Holding reg 2) — grant remote permission
2. In same FC16 frame or immediately after: Write `InvOpMod = 308` (Holding reg 0)

**STOP sequence (OperMode → 303):**
1. Write `RemRdy = 303` (Holding reg 2) — revoke remote permission
2. Write `InvOpMod = 303` (Holding reg 0)

**ErrClr one-shot rule:**  
Write `ErrClr (reg 8) = 26` in **exactly one OB30 scan** (≥100 ms after fault cleared), then write 0 in all subsequent scans. The SMA requires a 0 → 26 rising edge. Continuous writing of 26 will not re-acknowledge.

---

## 3. READ from SMA Inverter — FC04 (Inverter → PLC)

Read every OB30 cycle. On timeout or Modbus exception: set `CommError = TRUE` and hold last valid values.

### 3.1 Status and State Registers

| UDT Field | SMA Channel | Reg Addr (DEC) | Words | Data Type | Format | Unit | Derivation |
|---|---|---|---|---|---|---|---|
| `RemReady` | `OpStt` | **98** | 2 | S32 | ENUM | — | TRUE when OpStt ∈ {3526, 3527, 3530} |
| `Error` | `ErrStt` | **94** | 2 | S32 | ENUM | — | TRUE when ErrStt ≠ 307 |
| `PwrOffReas` | `PwrOffReas` | **178** | 2 | S32 | ENUM | — | 21626 = Low Power SetPoint |
| `DrtStt` | `DrtStt` | **176** | 2 | S32 | ENUM | — | 0/973 = no derating |
| *(SCADA log)* | `ErrNo` | **96** | 2 | U32 | FIX0 | — | Fault code — log when Error=TRUE |
| *(SCADA log)* | `ErrLcn` | **92** | 2 | U32 | ENUM | — | Fault location code |

### 3.2 Measured Power Registers

| UDT Field | SMA Channel | Reg Addr (DEC) | Words | Data Type | Format | Unit | Notes |
|---|---|---|---|---|---|---|---|
| `Wactive` | `InvMs.TotW` | **28** | 2 | S32 | FIX0 | kW | Measured AC active power output |
| `Qactive` | `InvMs.TotVAr` | **30** | 2 | S32 | FIX0 | kVAr | Measured AC reactive power output |
| *(display)* | `InvMs.TotVA` | **26** | 2 | S32 | FIX0 | kVA | Apparent power |
| *(display)* | `InvMs.PF` | **24** | 2 | S32 | FIX4 | — | Measured power factor ×10000 |
| *(display)* | `GriMs.Hz` | **38** | 2 | S32 | FIX2 | Hz | Grid frequency ×100 |

### 3.3 Availability and Setpoint Readback Registers

| UDT Field | SMA Channel | Reg Addr (DEC) | Words | Data Type | Format | Unit | Notes |
|---|---|---|---|---|---|---|---|
| `WAval` | `WAval` | **172** | 2 | S32 | FIX4 | pu×10000 | Available active power fraction. 10000 = 100% |
| `VArAval` | `VArAval` | **174** | 2 | S32 | FIX4 | pu×10000 | Available reactive power fraction |
| *(readback)* | `WSpt` | **108** | 2 | S32 | FIX0 | kW | Active power setpoint currently in effect |
| *(readback)* | `VArSpt` | **112** | 2 | S32 | FIX0 | kVAr | Reactive power setpoint currently in effect |
| *(readback)* | `PFSpt` | **114** | 2 | S32 | FIX4 | — | Power factor setpoint currently in effect |
| *(commiss.)* | `WRtg` | **184** | 2 | S32 | FIX0 | kW | Rated active power — read once at commissioning |

### 3.4 OpStt ENUM Decoding → RemReady

`RemReady` is derived from `OpStt` (Input reg 98):

| `OpStt` Value | Text | `RemReady` | Notes |
|---|---|---|---|
| **3526** | GridFeed | **TRUE** | Producing power — normal operation |
| **3527** | FRT | **TRUE** | Fault ride-through active |
| **3530** | RampDown | **TRUE** | Controlled ramp-down (still connected) |
| 3529 | QonDemand | TRUE | Reactive-only mode |
| 3528 | Standby | FALSE | Not producing |
| 1394 | WaitAC | FALSE | Waiting for AC grid |
| 1393 | WaitDC | FALSE | Waiting for DC voltage |
| 3524 | ConnectAC | FALSE | AC synchronising |
| 3525 | ConnectDC | FALSE | DC precharge |
| 381 | Stop | FALSE | Stopped |
| 1392 | Error | FALSE | Fault condition |
| 1787 | Init | FALSE | Booting |
| 1469 | ShutDown | FALSE | Shutting down |
| Other | — | FALSE | Unknown/transitioning |

> **Important:** Values 308 and 309 are NOT valid OpStt codes. They are InvOpMod/RemRdy ENUM codes. Earlier document versions incorrectly used them for OpStt.

### 3.5 ErrStt Derivation

```
Error := (ErrStt <> 307)
```

| `ErrStt` Value | Text | `Error` |
|---|---|---|
| **307** | OK | FALSE |
| **1392** | Error | TRUE |

### 3.6 DrtStt Key Values (Derating Active)

| Value | Text | PPC action |
|---|---|---|
| 973 | --- | No derating — normal dispatch |
| 21586 | Frt | FRT dynamic support — hold setpoints |
| 21601 | WCtlVol | P limited by grid voltage — accept constraint |
| 21651 | VArPrio | P reduced due to Q priority — accept constraint |
| 21591 | WCtlHz | Overfrequency P limitation |
| 21590 | WCtlLoHz | Underfrequency P limitation |

### 3.7 PwrOffReas Key Values

| Value | Text | PPC action |
|---|---|---|
| 21626 | Low Power SetPoint | Increase WSpt or VArSpt above inverter minimum threshold |
| 21609 | Stop: SCADA/PPC Modbus | Stop was commanded — restart only on operator request |
| 21607 | Stop: InvOpMod | InvOpMod not set to Operation — write 308 |
| 21617 | Standby: RemRdy | RemRdy not Ready — write 308 |
| 21615 | Standby: External Grid Error | External grid error signal present |
| 21612 | Standby: SCADA/PPC Modbus | Standby was commanded |
| 21613 | Standby: AC Synchronization | AC grid sync issue |

---

## 4. FB16 FSM — Read and Write State Machine (TIA Portal Implementation)

FB16 `InverterControl` uses a `FunctionalStateMachine` with **6 states** per inverter cycle. States 1–3 read (Unit ID 3), states 4–6 write (UID2 setpoints + UID3 event-driven mode). The FSM advances on each `MB_CLIENT` `done` rising edge. All inverter instances run in parallel (each has its own IDB and TCP connection). `MB_Unit_ID` is set per state.

> **MB_CLIENT modbusMode encoding:** `100 + Modbus FC#` — mode 103 = FC03, mode 104 = FC04, mode 116 = FC16. Using mode 1 instead of 116 caused all FC16 writes to fail silently. Fixed 2026-08-15.

### 4.1 v2.0 FSM (current)

| State | Direction | FC | Unit ID | Modbus Addr | Words | Data mapped |
|---|---|---|---|---|---|---|
| 1 | READ  | FC03 (mode 103) | 3 | 0   | 104 | Holding regs → Inverter UDT + ParamHold |
| 2 | READ  | FC04 (mode 104) | 3 | 10  | 106 | Input regs → ParamInputs + Inverter measurements |
| 3 | READ  | FC04 (mode 104) | 3 | 116 | 112 | Input regs continued → ParamInputs |
| 4 | WRITE | FC16 (mode 116) | **2** | **22** | **2** | VArSpt_pct (S16) + WSpt_pct (S16) — cyclic fast setpoints |
| 5 | WRITE | FC16 (mode 116) | **2** | **24** | **3** | PF_cos (U16) + PF_excitation (U32) — PF mode only |
| 6 | WRITE | FC16 (mode 116) | **3** | 0   | 10  | InvOpMod, RemRdy, VArMod, WMod, ErrClr — **event-driven** |

> State 6 is gated by a change-detect latch: only executes when any mode/command field has changed since last write. Prevents non-volatile storage wear.

### 4.2 v1.9 FSM (DEPRECATED — transition reference only)

| State | Direction | FC | Unit ID | Modbus Addr | Words | Data mapped |
|---|---|---|---|---|---|---|
| 1 | READ  | FC03 (mode 103) | 3 | 0   | 104 | Holding regs |
| 2 | READ  | FC04 (mode 104) | 3 | 10  | 106 | Input regs |
| 3 | READ  | FC04 (mode 104) | 3 | 116 | 112 | Input regs continued |
| 4 | WRITE | FC16 (mode 116) | 3 | 0   | 10  | InvOpMod, RemRdy, VArMod, WMod, ErrClr |
| 5 | WRITE | FC16 (mode 116) | 3 | 108 | 2   | WSpt (kW, FIX0) |
| 6 | WRITE | FC16 (mode 116) | 3 | 112 | 4   | VArSpt (kVAr, FIX0) + PFSpt (FIX4) |

### 4.3 Write Buffer Packing — FC_Pack_Write_Regs

Before each write state the helper FC `FC_Pack_Write_Regs` is called (on the one-scan `FSM_DB.Transition` pulse) to pack the SKID_DB setpoint values into `holdingRegisterMod[]` for `MB_CLIENT`.

**v2.0 WriteSteps:**

```
WriteStep_UID2_SetPt → holdingRegisterMod[0..1]  (State 4: UID2 addr 22-23)
  [0] = VArSpt_pct (S16 raw, INT_TO_WORD)
  [1] = WSpt_pct   (S16 raw, INT_TO_WORD)

WriteStep_UID2_PF    → holdingRegisterMod[0..2]  (State 5: UID2 addr 24-26)
  [0] = PF_cos      (U16 FIX4, WORD)
  [1] = PF_excit HW (high word of U32 ENUM)
  [2] = PF_excit LW (low word of U32 ENUM)

WriteStep_UID3_Mode  → holdingRegisterMod[0..9]  (State 6: UID3 addr 0-9)
  — same as v1.9 WriteStep 1 (InvOpMod, RemRdy, VArMod, WMod, ErrClr as S32 word pairs)
```

**v1.9 WriteSteps (deprecated — keep until v2.0 validated):**

```
WriteStep 1 → holdingRegisterMod[0..9]  (v1.9 State 4: UID3 regs 0-9)
WriteStep 2 → holdingRegisterMod[0..1]  (v1.9 State 5: UID3 regs 108-109)
WriteStep 3 → holdingRegisterMod[0..3]  (v1.9 State 6: UID3 regs 112-115)
```

### 4.2 FC17 Race Condition Fix — WSpt/VArSpt/PFSpt Readback

`FC_InputReg10_L106_To_Inputs` (FC17) previously wrote reg 108/112/114 readbacks into `Inv.WSpt`, `Inv.VArSpt`, `Inv.PFSpt` — the same fields PPC uses for commands. This would silently overwrite PPC setpoints before State 5/6 could send them.

**Fix applied (Option B):** Three lines in FC17 redirected to new fields in `Skid_Parameters_Inputs` UDT:

| FC17 line | Was | Now |
|---|---|---|
| 174–175 | `#Inv."WSpt" := #di32` | `#Inps."WSpt_Fdbk" := #di32` |
| 190–191 | `#Inv."VArSpt" := #di32` | `#Inps."VArSpt_Fdbk" := #di32` |
| 194–195 | `#Inv."PFSpt" := DINT_TO_REAL(#di32)/10000.0` | `#Inps."PFSpt_Fdbk" := DINT_TO_REAL(#di32)/10000.0` |

New fields added to `Skid_Parameters_Inputs` UDT: `WSpt_Fdbk : DInt`, `VArSpt_Fdbk : DInt`, `PFSpt_Fdbk : Real`.  
`Inv.WSpt`, `Inv.VArSpt`, `Inv.PFSpt` are now **exclusively owned by PPC** (command values). The readback confirmation is available in `Inps.WSpt_Fdbk` etc.

---

## 5. Local PLC Fields — NOT from Modbus

These UDT fields are managed entirely within the PLC. The comms block must **NOT** overwrite them.

| UDT Field | Source | Description |
|---|---|---|
| `Enabled` | HMI / DB39 operator | Set TRUE to include inverter in PPC. |
| `CommError` | Comms block itself | TRUE if no valid Modbus response in ≥3 consecutive scans. Cleared on next successful response. |

---

## 6. DB39 Fields Used by PPC Logic

### IEC_Watchdog — FB_PPC_Controller input

`IEC_Watchdog : Bool` is the **upstream communication alive** signal wired to `FB_PPC_Controller`. When `FALSE`, the PPC controller stops following remote setpoints and falls back to safe mode.

| Upstream link | Wire IEC_Watchdog from |
|---|---|
| IEC 60870-5-104 (CP module) | `CP_Block.Connected AND CP_Block.DataValid` |
| IEC 60870-5-104 software stack | Stack connection status + data-age check |
| Modbus TCP from SCADA | Modbus server `Connected` bit |
| Profinet / OPC UA from EMS | IO quality / subscription status bit |
| Commissioning (no upstream yet) | Manual Bool bit e.g. `%M300.0` set from HMI |

**Recommended implementation — retriggerable timer (any protocol):**

```pascal
// In OB30 — reset timer each time SCADA sends a new message/heartbeat
"IEC_WD_Timer"(IN := NOT "SCADA_NewDataReceived",
               PT := T#30S);
IEC_Watchdog := NOT "IEC_WD_Timer".Q;
// If no new data within 30 s → Timer.Q=TRUE → IEC_Watchdog=FALSE → PPC safe mode
```

> **Never hardwire IEC_Watchdog to TRUE in production.** Its purpose is to detect upstream failure and prevent the PPC from acting on stale setpoints.

---

### Set by SCADA / HMI (inputs to PPC):

| DB39 Field | Type | Description | Source |
|---|---|---|---|
| `START_CONTROLLER` | Bool | Master enable → `EN_PPC` FB input | HMI |
| `Targets_P` | Real | Active power setpoint from SCADA (kW) | SCADA (REMOTE) / HMI (LOCAL) |
| `Targets_Q` | Real | Reactive power setpoint (kVAr) | SCADA / HMI |
| `Targets_PF` | Real | Power factor setpoint | SCADA / HMI |
| `P_RampUp` | Real | Active power ramp-up rate (kW/s) | Engineering / HMI |
| `P_RampDown` | Real | Active power ramp-down rate (kW/s) | Engineering / HMI |
| `Q_Ramp` | Real | Reactive power ramp rate (kVAr/s) | Engineering / HMI |
| `WRtg_kW` | Real | Rated power per inverter (kW) — read from reg 184 at commissioning | Engineering |
| `Plant_P_meas` | Real | Plant-level active power at PCC (kW) — from energy meter | Meter |
| `Plant_Q_meas` | Real | Plant-level reactive power at PCC (kVAr) | Meter |

### Written by PPC logic (outputs for HMI/SCADA):

| DB39 Field | Type | Description |
|---|---|---|
| `Plant_Mode` | Int | 0=LOCAL, 1=REMOTE, 2=FALLBACK |
| `Plant_N_Online` | Int | Count of inverters currently online |
| `Limits_PmaxPlant` | Real | Total available active power (kW) |
| `Limits_QmaxPlant` | Real | Total available reactive power (kVAr) |
| `Ramps_Pcmd` | Real | Rate-limited active power command (kW) |
| `Ramps_Qcmd` | Real | Rate-limited reactive power command (kVAr) |
| `AnyFault` | Bool | TRUE = at least one inverter fault or comm error |
| `AnyDerating` | Bool | TRUE = at least one inverter is derated |
| `FaultMask` | Word | Bit i = inverter i has active fault or comm error |

---

## 7. Per-Inverter Write Transaction (corrected)

Each OB30 cycle the comms block performs the following FC16 writes for each online inverter:

```scl
// --- Step 1: Fault clear (one-shot) ---
IF ErrClr <> 0 THEN
    Write Holding[8] = 26          // ErrClr = Ackn
ELSE
    Write Holding[8] = 0           // ErrClr = idle
END_IF

// --- Step 2: Mode changes and start/stop sequencing ---
IF OperMode = 303 THEN             // Stop sequence
    Write Holding[2] = 303         // RemRdy = Standby
    Write Holding[0] = 303         // InvOpMod = Stop
ELSIF OperMode = 308 THEN          // Start sequence
    Write Holding[2] = 308         // RemRdy = Ready
    Write Holding[0] = 308         // InvOpMod = Operation
END_IF

// --- Step 3: Control modes ---
Write Holding[6] = WMode           // GriMng.WMod  (1079=WCtlCom, 303=Off)
Write Holding[4] = VArMode         // GriMng.VArMod (1072=VArCtlCom, 1075=PFCtlCom)

// --- Step 4: Setpoints (CORRECTED — NOT GriMng.WNom/VArNom/PFNom) ---
Write [108] = WSpt                 // Active power setpoint (kW, FIX0)
Write [112] = VArSpt               // Reactive power setpoint (kVAr, FIX0) [if VArCtlCom]
Write [114] = PFSpt                // Power factor setpoint (×10000)         [if PFCtlCom]
```

---

## 8. Per-Inverter Read Transaction (corrected)

Each OB30 cycle, read via FC04:

```scl
// Batch read 1: addresses 10 to 115 (106 words)
Read [28]  → Wactive   (kW,    FIX0)   // InvMs.TotW
Read [30]  → Qactive   (kVAr,  FIX0)   // InvMs.TotVAr
Read [94]  → ErrStt    (ENUM)          // Error := (ErrStt <> 307)
Read [96]  → ErrNo     (FIX0)          // Log on Error
Read [98]  → OpStt     (ENUM)          // RemReady := (OpStt IN {3526,3527,3530})
Read [108] → WSpt_rb   (kW,    FIX0)   // Setpoint readback
Read [112] → VArSpt_rb (kVAr,  FIX0)
Read [114] → PFSpt_rb  (FIX4)

// Batch read 2: addresses 116 to 227 (112 words)
Read [172] → WAval     (pu,  FIX4)    // ÷10000 for fraction
Read [174] → VArAval   (pu,  FIX4)
Read [176] → DrtStt    (ENUM)         // 973 = none
Read [178] → PwrOffReas(ENUM)         // 21626 = Low Power SetPoint
Read [184] → WRtg      (kW,  FIX0)   // Read once at startup

// --- Communication error handling ---
IF timeout OR Modbus_Exception THEN
    CommError := TRUE
    // All UDT fields retain last valid values
    // Block setpoint writes for this inverter until CommError clears
END_IF
// CommError cleared on next successful read
```

---

---

## 9. AuxCtl.LifeSign — SMA Inverter Application Watchdog

The SMA Sunny Central monitors a **lifesign counter** written by the Modbus master. If it stops incrementing for the configured timeout (`WtTms`, typically 60 s), the inverter drops out of remote control mode and ignores PPC setpoints.

| Item | Value |
|---|---|
| SMA channel | `AuxCtl.LifeSign` |
| Direction | PLC → Inverter (FC16 write) |
| Data type | S16 (Int) |
| Action | Increment by 1 each OB30 cycle, wrap 32767 → 0 |
| Timeout | `WtTms` parameter in SMA (default 60 s) |

**Implementation:** Add a State 7 to the FB15 FSM or include the LifeSign address in the State 4 write block if the address is contiguous. In OB30, before calling FC19:

```pascal
"SKID1".LifeSign := "SKID1".LifeSign + 1;   // repeat for SKID2..SKID10
```

> The readback of `AuxCtl.LifeSign` is already present in `Skid_Parameters_Inputs.AuxCtl.LifeSign` (mapped by FC17). Verify the SMA register address for the write from the SMA Modbus register map.

---

*Document version: updated 2026-08-16 | v2.0 porting: dual Unit ID architecture, UID2 % setpoints (FIX2), event-driven UID3 mode writes, v1.9 deprecated sections retained for transition | Source: MODBUS-SC-TI-en-20 (v2.0, firmware 10.03.14.R) + MODBUS-SCxxxx-TI-en-19 (v1.9)*
