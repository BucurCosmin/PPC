# SMA Sunny Central — Modbus Comms Block Mapping (Corrected)

**Target:** PPC_Controller [DB39], UDT `Inverter_controller`  
**Connection:** Modbus TCP, Unit ID = 3  
**Source:** `SMA\MODBUS-SCxxxx-TI-en-19.pdf` + `SMA\SCADA_Modbus_Register_Map_SMA_SunnyCentral_ENUMS_Ramps_RideThrough_PPC_RO.xlsx`  

> **Correction note:** Previous version incorrectly referenced `GriMng.WNom`, `GriMng.VArNom`, and `GriMng.PFNom` for active power, reactive power, and power factor setpoints. These names **do not exist** in the SMA Modbus profile. The correct register names are `WSpt` (address 108), `VArSpt` (address 112), and `PFSpt` (address 114). Previous version also used wrong OpStt ENUM codes (308/309) — corrected to the actual SMA values (3526/3527).

---

## 1. Conventions

| Item | Value |
|---|---|
| Modbus protocol | TCP/IP |
| Unit (Slave) ID | 3 |
| Register bit-width | 32-bit values — each occupies **2 consecutive 16-bit registers** |
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
| FIX0 | ×1 — value in physical units | WSpt: 500 → 500 kW |
| FIX1 | ×10 | GriMs.Hz: 5000 → 50.00 Hz |
| FIX2 | ×100 | — |
| FIX4 | ×10000 | PFSpt: 9500 → PF 0.9500 |

**Register address note:** WSpt, VArSpt, and PFSpt appear in the SMA register map as *Input Register* readbacks (FC04, read-only). SMA Sunny Central also accepts FC16 writes to these same addresses when the corresponding control mode (WCtlCom / VArCtlCom / PFCtlCom) is active. The FC04 readback confirms what setpoint the inverter is currently tracking.

---

## 2. WRITE to SMA Inverter — FC16 (PLC → Inverter)

Written every OB30 cycle (except ErrClr which is one-shot only).

| # | UDT Field | SMA Channel | Reg Addr (DEC) | Words | Data Type | Format | Unit | Written by |
|---|---|---|---|---|---|---|---|---|
| 1 | *(derived)* | `RemRdy` | **2** | 2 | S32 | ENUM | — | Comms block (derived from OperMode) |
| 2 | `OperMode` | `InvOpMod` | **0** | 2 | S32 | ENUM | — | FaultHandler |
| 3 | `WMode` | `GriMng.WMod` | **6** | 2 | S32 | ENUM | — | PowerDistribution |
| 4 | `VArMode` | `GriMng.VArMod` | **4** | 2 | S32 | ENUM | — | ReactiveControl |
| 5 | `WSpt` | `WSpt` | **108** | 2 | S32 | FIX0 | kW | PowerDistribution |
| 6 | `VArSpt` | `VArSpt` | **112** | 2 | S32 | FIX0 | kVAr | ReactiveControl |
| 7 | `PFSpt` | `PFSpt` | **114** | 2 | S32 | FIX4 | — | ReactiveControl |
| 8 | `ErrClr` | `ErrClr` | **8** | 2 | S32 | ENUM | — | FaultHandler (one-shot) |

> Note: RemRdy (reg 2) must always be written **before** InvOpMod (reg 0). Write in order: RemRdy → InvOpMod.

### 2.1 ENUM Values for Write Registers

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

### 2.2 Setpoint Scaling Examples

| UDT Value | Register Value | Physical Value |
|---|---|---|
| WSpt = 2000 | 2000 | 2000 kW |
| VArSpt = −500 | −500 | −500 kVAr (capacitive) |
| PFSpt = 0.95 | 9500 | cos φ = 0.950 (lagging) |
| PFSpt = 1.00 | 10000 | cos φ = 1.000 (unity) |

### 2.3 Critical Write Sequencing — SMA Interlock Rules

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

## 4. FB15 FSM — Read and Write State Machine (TIA Portal Implementation)

FB15 `ReadInverterData` uses a `FunctionalStateMachine` with **6 states** per inverter cycle. States 1–3 read, states 4–6 write. The FSM advances on each `MB_CLIENT` `done` rising edge. All 10 inverter instances run in parallel (each has its own IDB and TCP connection).

| State | Direction | FC | Modbus Addr | Words | Data mapped |
|---|---|---|---|---|---|
| 1 | READ  | FC03 (mode 103) | 0   | 104 | Holding regs → Inverter UDT + ParamHold |
| 2 | READ  | FC04 (mode 104) | 10  | 106 | Input regs → ParamInputs + Inverter measurements |
| 3 | READ  | FC04 (mode 104) | 116 | 112 | Input regs continued → ParamInputs |
| 4 | WRITE | FC16 (mode 1)   | 0   | 10  | InvOpMod, RemRdy, VArMod, WMod, ErrClr |
| 5 | WRITE | FC16 (mode 1)   | 108 | 2   | WSpt |
| 6 | WRITE | FC16 (mode 1)   | 112 | 4   | VArSpt + PFSpt |

> Regs 110–111 (gap between WSpt and VArSpt) are **not written** — states 5 and 6 are intentionally separate transactions to avoid writing unknown registers.

### 4.1 Write Buffer Packing — FC_Pack_Write_Regs

Before each write state the helper FC `FC_Pack_Write_Regs` is called (on the one-scan `FSM_DB.Transition` pulse) to pack the SKID_DB setpoint values into `holdingRegisterMod[]` for `MB_CLIENT`. Every DInt is split into two big-endian Words (high word at lower buffer index). PFSpt Real is scaled ×10000 before packing.

```
WriteStep 1 → holdingRegisterMod[0..9]  (states 4 write: regs 0-9)
WriteStep 2 → holdingRegisterMod[0..1]  (state 5 write: reg 108-109)
WriteStep 3 → holdingRegisterMod[0..3]  (state 6 write: regs 112-115)
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

*Document version: updated 2026-06-04 | Additions: FB15 6-state FSM, FC17 race condition fix, FC_Pack_Write_Regs, IEC_Watchdog, AuxCtl.LifeSign watchdog | Source: MODBUS-SCxxxx-TI-en-19 §5.3 + SCADA Register Map XLSX*
