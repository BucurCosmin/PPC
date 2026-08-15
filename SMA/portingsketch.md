# SMA Modbus v1.9 → v2.0 Porting Sketch

**Branch:** SMAv20  
**Source:** SMAv19toV20.md analysis + MODBUS-SC-TI-en-20.pdf  
**Date:** 2026-08-15  
**Status:** DRAFT — resolve open questions before implementing

---

## 0. Open questions that must be answered FIRST

Before any code changes, these must be confirmed against the actual v2.0 PDF:

| # | Question | Why it matters |
|---|---|---|
| Q1 | Are the Unit ID 2 addresses (40022, 40023…) in **1-based** (40001 = first reg) or **0-based** PDU format? | Our MB_CLIENT uses 0-based; wrong address = wrong register |
| Q2 | Does Unit ID 2 use the **same TCP connection** as Unit ID 3, or does it need a **separate socket**? | Determines if FB16 can reuse one connection or needs two |
| Q3 | Are Unit ID 3 WSpt (reg 108) and VArSpt (reg 112) still valid write targets in v2.0, or deprecated? | If deprecated, old FSM states 5/6 must be changed entirely |
| Q4 | What **firmware version** is installed on the SC 4600 UP units on site? | v2.0 requires firmware ≥ 10.03.xx.R |
| Q5 | WSpt/VArSpt at Unit ID 2 are S16 FIX2 (%). What is the **reference value** (`WExlSpt.RefVal` / `VArExlSpt.RefVal`) read from and at what register address? | Needed to convert kW → % for the write |
| Q6 | For PF control: v2.0 uses reg 40024 + 40025 at Unit ID 2. Is the existing Unit ID 3 PFSpt (reg 114) still valid? | Affects PF write path |
| Q7 | Is `VolNomSpt` (Unit ID 2, reg 41263) **needed for U control** (mode 3), or does our existing Q-based PID via VArSpt remain better? | Architecture decision — not just porting |

---

## 1. What actually changed: the critical differences

### 1.1 Write target split (BIGGEST change)

| Signal | v1.9 | v2.0 |
|---|---|---|
| WSpt | Unit ID 3, reg 108, S32 FIX0 kW | Unit ID 2, reg 40023, **S16 FIX2 %** |
| VArSpt | Unit ID 3, reg 112, S32 FIX0 kVAr | Unit ID 2, reg 40022, **S16 FIX2 %** |
| PF magnitude | Unit ID 3, reg 114, S32 FIX4 | Unit ID 2, reg 40024, **U16 FIX4** |
| PF excitation | (not separate) | Unit ID 2, reg 40025, U32 ENUM |
| VolNomSpt | (not available) | Unit ID 2, reg 41263, U16 FIX4 p.u. |
| HzNomSpt | (not available) | Unit ID 2, reg 41261, U32 FIX3 Hz |
| WSptMax | (not available) | Unit ID 2, reg 44039, S32 FIX2 % |
| WSptMin | (not available) | Unit ID 2, reg 44041, S32 FIX2 % |

Mode/config registers (Unit ID 3: InvOpMod, RemRdy, GriMng.VArMod, GriMng.WMod) remain at Unit ID 3 but must become **event-driven** (write only on change), not cyclic.

### 1.2 Parameter vs Setpoint discipline (v2.0 explicit rule)

```
CYCLIC (100 ms):
    WSpt, VArSpt → Unit ID 2
    PF cmd → Unit ID 2
    VolNomSpt (if U-control mode active) → Unit ID 2

EVENT-DRIVEN (only on change):
    GriMng.WMod → Unit ID 3
    GriMng.VArMod → Unit ID 3
    InvOpMod, RemRdy → Unit ID 3
    Any other parameter register

CYCLIC READ (100 ms):
    Measurements (P, Q, OpStt, ErrStt) → Unit ID 3

SLOW READ (1–10 s):
    Availability, derating, fallback status → Unit ID 3
```

Writing parameters every 100 ms (as we currently do) updates the SMA's non-volatile storage and is explicitly prohibited in v2.0.

---

## 2. Scope of changes by file / block

### 2.1 FB16 InverterControl (TIA Portal — LAD)

**Current FSM (6 states):**
```
State 1: FC03 read, UID3, addr=0,   len=104  (holdings)
State 2: FC04 read, UID3, addr=10,  len=106  (inputs)
State 3: FC04 read, UID3, addr=116, len=112  (inputs cont.)
State 4: FC16 write,UID3, addr=0,   len=10   (InvOpMod, RemRdy, VArMod, WMod, ErrClr)
State 5: FC16 write,UID3, addr=108, len=2    (WSpt kW)
State 6: FC16 write,UID3, addr=112, len=4    (VArSpt + PFSpt)
```

**Required new FSM (TBD states):**
```
State 1: FC03 read, UID3, addr=0,   len=104  (holdings — same)
State 2: FC04 read, UID3, addr=10,  len=106  (inputs — same)
State 3: FC04 read, UID3, addr=116, len=112  (inputs cont. — same)
State 4: FC03 read, UID2, addr=?,   len=?    (NEW: read RefVal + Unit ID 2 feedback)
State 5: FC16 write,UID2, addr=?,   len=?    (NEW: WSpt % + VArSpt % fast setpoints)
State 6: FC16 write,UID2, addr=?,   len=?    (NEW: PF cmd and/or VolNomSpt if needed)
State 7: FC16 write,UID3, addr=0,   len=10   (InvOpMod, RemRdy — EVENT DRIVEN, not every cycle)
```

> ⚠️ State 7 (old mode write) must be gated: only write when mode has changed, not every 100 ms.  
> ⚠️ Old States 5+6 (Unit ID 3 WSpt/VArSpt kW writes) — keep or remove pending Q3 answer.

**Changes in FB16:**
- Add new states for Unit ID 2 reads and writes
- Change `Client_DB.MB_Unit_ID` assignment per state (2 or 3)
- Gate mode-parameter write (State 7) on a "mode-changed" latch flag
- modbusMode stays 103/104/116 convention

### 2.2 FC_Pack_Write_Regs (TIA Portal SCL or LAD)

**Current WriteStep 1/2/3** pack Unit ID 3 values (S32 kW/kVAr, big-endian word pairs).

**New write steps needed:**
- `WriteStep_UID2_SetPt`: pack S16 WSpt% + S16 VArSpt% into 2 words
- `WriteStep_UID2_PF`: pack U16 PF + U32 excitation type into 3 words
- `WriteStep_UID2_VolSpt` (optional, only if U-control uses VolNomSpt)

**Scaling logic to add:**
```
WSpt_pct_raw := REAL_TO_INT(Inverter.WSpt_kW / WExlSpt_RefVal_kW * 10000.0)
    // S16 FIX2 → value 10000 = 100.00%
VArSpt_pct_raw := REAL_TO_INT(Inverter.VArSpt_kVar / VArExlSpt_RefVal_kVar * 10000.0)
```
> ⚠️ Exact FIX2 scaling factor to verify against v2.0 PDF (FIX2 means ×100 or ×10000?)

### 2.3 FC_PPC_SkidMapping.scl

**Write direction changes:**
- Remove cyclic writes to `SkidInverter.WSpt` (kW) and `SkidInverter.VArSpt` (kVAr) for Unit ID 3
- Add new fields: `SkidInverter.WSpt_pct` (S16), `SkidInverter.VArSpt_pct` (S16)
- Add scaling: convert `Inverter.WSpt` (kW) → `WSpt_pct` using `WExlSpt_RefVal`
- Mode writes (InvOpMod, RemRdy, VArMod, WMod) must be conditioned on change-detect flag, not written every scan

**Read direction changes (Unit ID 2 feedback to add):**
- Map `WExlSpt.RefVal` from Skid → Inverter UDT (for scaling validation)
- Map `VArExlSpt.RefVal` similarly
- Map `WSptMax_fdbk`, `WSptMin_fdbk` if WSptMax/WSptMin are implemented

### 2.4 Sunny_inverter UDT (TIA Portal)

New fields needed:
```
WSpt_pct        : Int      // S16 — v2.0 Unit ID 2 write format
VArSpt_pct      : Int      // S16 — v2.0 Unit ID 2 write format
PF_cos          : Word     // U16 FIX4 — cos(phi) for Unit ID 2
PF_excitation   : DWord    // U32 ENUM — over/underexcited
WExlSpt_RefVal  : DInt     // kW reference for scaling (read from UID3)
VArExlSpt_RefVal: DInt     // kVAr reference for scaling (read from UID3)
ExtdFlbStt      : DInt     // extended fallback status (UID3 reg 286)
WSptMin_fdbk    : DInt     // effective P min from inverter (UID3 reg 338)
WSptMax_fdbk    : DInt     // effective P max from inverter (UID3 reg 339)
```

Optionally (if U-control via VolNomSpt):
```
VolNomSpt       : Word     // U16 FIX4 p.u. — for UID2 write
```

### 2.5 Inverter_controller UDT (PPC side)

Fields to verify / add:
```
WSptMax         : Real     // plant P ceiling from grid operator (kW, maps → UID2 WSptMax)
WSptMin         : Real     // plant P floor (kW, maps → UID2 WSptMin)
ExtdFlbStt      : DInt     // fallback status passthrough
WSptMin_fdbk    : Real     // effective Pmin readback (for dispatcher)
WSptMax_fdbk    : Real     // effective Pmax readback (for dispatcher)
```

### 2.6 Modbus_Comms_Mapping.md

Full rewrite of Section 2 (WRITE), Section 3 (READ), Section 4 (FSM table) for v2.0.  
Key additions:
- Unit ID 2 register table (setpoints + reference values)
- Scaling formulas for FIX2 % format
- Parameter vs setpoint classification for every register
- Updated FSM state table

### 2.7 PPC_FUNCTIONAL_DESCRIPTION.md + PPC_Sequence_Diagram.md

- Update Modbus write section to show Unit ID 2 path for setpoints
- Add note on parameter-write discipline (event-driven)
- Add fallback register group description
- WSptMax / WSptMin integration into dispatch logic description

---

## 3. What does NOT change

- modbusMode encoding (100 + FC#) — stays the same
- Read path for measurements (InvMs.TotW, InvMs.TotVAr, OpStt, ErrStt, WAval, VArAval) — same registers, Unit ID 3
- MB_CLIENT instance, TCP connection setup, FSM engine — same structure
- FC_PPC_SkidMapping read direction — same field mapping
- FB_PPC_Controller control modes (0–3) — same logic, only scaling/write path changes
- U control mode 3 PID — still Q-based via VArSpt (just % now instead of kVAr)
- ANRE droop / FRT logic — unchanged

---

## 4. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Firmware < 10.03.xx.R on site inverters | **CRITICAL** | Check firmware version before any v2.0 write attempt |
| Unit ID 2 requires separate TCP socket | High | Test with external Modbus tool on UID2 before FB16 changes |
| FIX2 scaling wrong (100 vs 10000) | High | Verify against PDF + test with small setpoint |
| Unit ID 3 WSpt/VArSpt deprecated in v2.0 — old states left in FSM | Medium | Test both paths, remove old if confirmed deprecated |
| Mode write becoming non-volatile damage | Medium | Gate State 7 write on change-detect latch from day 1 |
| WExlSpt.RefVal address wrong | Medium | Verify exact 0-based PDU address from v2.0 PDF |
| 40022/40023 address interpretation error | High | Q1 must be answered — test with external tool first |

---

## 5. Suggested implementation order

```
Step 1  Answer Q1–Q7 (read v2.0 PDF, test with external Modbus tool)
Step 2  Update Modbus_Comms_Mapping.md with confirmed v2.0 register table
Step 3  Add new UDT fields (Sunny_inverter + Inverter_controller)
Step 4  Add Unit ID 2 read state to FB16 (get RefVal before writing %)
Step 5  Add FC_Pack_Write_Regs WriteStep for Unit ID 2 % format
Step 6  Add Unit ID 2 write state(s) to FB16 FSM
Step 7  Update FC_PPC_SkidMapping write direction (scaling + new fields)
Step 8  Gate Unit ID 3 mode writes (event-driven)
Step 9  Test with one inverter: verify WSpt/VArSpt reach inverter correctly
Step 10 Update remaining documentation
```

---

## 6. Potential shortcuts / simplifications

- **Skip WSptMax / WSptMin initially** — implement basic P/Q setpoint path first, add limits later
- **Skip VolNomSpt for now** — U control mode 3 already works via Q setpoint (PID output → VArSpt %)
- **Skip HzNomSpt** — not needed for ANRE grid code at this time
- **Skip fallback ramp config** — implement fallback status read first, config later
- Keep Unit ID 3 WSpt/VArSpt writes as a **fallback path** until v2.0 path is validated on hardware

---

*This sketch is a starting point. Review against actual v2.0 PDF before committing to any implementation step.*
