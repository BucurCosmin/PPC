# FC_PPC_QCapability — Requirements Document

**Purpose:** P-Q reactive power capability control for the PPC, combining ANRE regulatory
compliance (Art. 150–152, Ordin ANRE 51) with SMA SC 4600 UP inverter physical limits.

**Status:** Draft for implementation in VSCode / Claude Code.

---

## 1. Regulatory basis (ANRE Ordin 51, Art. 150–152)

### Art. 150 — P-Q capability diagram determination (testing procedure)

To determine the theoretical P-Q diagram of the generating unit/plant at the connection
point, within the permissible voltage band, at a value as close as possible to installed
active power:

1. A maximum reactive power setpoint is applied in both inductive and capacitive mode.
   Values are recorded. The P-Q diagram continues to be plotted for **at least 5 active
   power points**.
2. For a **zero active power setpoint**, reactive power injected at the connection point
   is also measured, verifying it is **zero (null)**.
3. Measured values are recorded both at the substation (connection point) and at the
   generating unit level (P, Q, U, f), together with setpoint values.

### Art. 151 — U-Q/Pmax diagram

After the Art. 150 tests, the U-Q/Pmax diagram is also plotted.

### Art. 152 — Simulation requirement + zero-Q tolerance

1. In addition to physical tests, a **simulation** of reactive power capability is
   performed using the mathematical model of the generating unit/plant, demonstrating
   capability as both a P-Q diagram and a U-Q/Pmax diagram.
2. Simulation is successful if, cumulatively:
   - (a) the simulation model is validated against the compliance tests;
   - (b) compliance with the applicable technical standard is demonstrated;
   - (c) for a zero active power setpoint, reactive power injected at the connection
     point is measured and verified as zero, within tolerance:
     - **≤ 0.5 MVAr** for connection point nominal voltage ≥ 110 kV
     - **≤ 0.5 MVAr** for connection point < 110 kV, plant connected to substation busbars
     - **≤ 0.1 MVAr** for connection point < 110 kV, plant connected on lines / end of a
       long line

### What this means for the FB

| ANRE requirement | Implementation implication |
|---|---|
| P-Q diagram, ≥5 P points | Capability table must be interpolated smoothly across the full P range, not just a few hardcoded setpoints |
| Q measured at **connection point**, not inverter terminals | PPC-level correction needed — individual inverters cannot see or correct for transformer/cable reactive losses |
| Zero Q at P=0, within 0.1–0.5 MVAr | Requires either a feedforward compensation term or closed-loop POC trim, layered on top of the capability curve |
| U-Q/Pmax diagram | Capability limits must be a function of voltage, not just active power |
| Simulation validated against tests | The SCL capability model (interpolated table) *is* the "simulation model" — its accuracy against the physical inverter table is what gets validated during ISCE commissioning |

---

## 2. SMA SC 4600 UP — physical capability envelope

Source: SMA "Sunny Central and Sunny Central Storage — Reactive Power Capability",
Version 2021-03-22, Table 1 (SC 4600 UP).

**Key facts:**
- Nominal apparent power: Sn = 4600 kVA → Qmax = 0.6 × Sn = **2760 kVar** (cosφ = 0.8 limit)
- Qmax is available down to **~0.1% of Pn** (i.e., essentially P=0)
- Qmax is **not** temperature-dependent
- Apparent power (and therefore max P and the P-range over which full Qmax is
  available) **shrinks proportionally with grid voltage below Un**; voltages above Un
  give no extra capability

**Table shape:** for each voltage bin, Qmax is **flat at 2760 kVar** from P=0 up to a
breakpoint, then **tapers** as P approaches Pmax (apparent-power/current limit:
`Qmax = sqrt(Smax² − P²)`).

### 2.1 Capability breakpoints by voltage (SC 4600 UP)

| Ugrid (p.u. Un) | Pmax available [kW] | P at start of taper [kW] (Q still = Qmax) | Qmax flat region [kVar] |
|---|---|---|---|
| 0.85 | 3911.0 | ~2933 (last flat point) | 2760.0 |
| 0.90 | 4141.1 | ~3106 | 2760.0 |
| 0.95 | 4371.1 | ~3278 | 2760.0 |
| 1.00 – 1.15 | 4600.0 | ~3680 | 2760.0 |

> Note: Qmax stays at the full 2760 kVar even down to P=0 at every voltage — the
> inverter is **not** the limiting factor for the Art. 152(2)(c) zero-P/zero-Q
> requirement. Any nonzero Q measured at the POC at P=0 comes from transformer
> magnetizing current, cable charging, or other plant-level reactive sources — see
> §4 below.

### 2.2 Full lookup table — SC 4600 UP (Pbin / Qoverexcited pairs)

Symmetric: `Qunderexcited = −Qoverexcited`. All values as given in the SMA datasheet
(comma decimal converted to point).

**Ugrid = 0.85 p.u. Un**

| P [kW] | Qmax [kVar] |
|---|---|
| 3911.0 | 0.0 |
| 3715.5 | 1221.2 |
| 3519.9 | 1704.8 |
| 3324.4 | 2060.3 |
| 3128.8 | 2346.6 |
| 2933.3 | 2586.9 |
| 2737.7 | 2760.0 |
| 2542.2 | 2760.0 |
| 2346.6 | 2760.0 |
| 2151.1 | 2760.0 |
| 1955.5 | 2760.0 |
| 1760.0 | 2760.0 |
| 1564.4 | 2760.0 |
| 1368.9 | 2760.0 |
| 1173.3 | 2760.0 |
| 977.8 | 2760.0 |
| 782.2 | 2760.0 |
| 586.7 | 2760.0 |
| 391.1 | 2760.0 |
| 195.6 | 2760.0 |
| 0.0 | 2760.0 |

**Ugrid = 0.90 p.u. Un**

| P [kW] | Qmax [kVar] |
|---|---|
| 4141.1 | 0.0 |
| 3934.0 | 1293.0 |
| 3727.0 | 1805.1 |
| 3519.9 | 2181.4 |
| 3312.9 | 2484.6 |
| 3105.8 | 2739.1 |
| 2898.8 | 2760.0 |
| 2691.7 | 2760.0 |
| 2484.6 | 2760.0 |
| 2277.6 | 2760.0 |
| 2070.5 | 2760.0 |
| 1863.5 | 2760.0 |
| 1656.4 | 2760.0 |
| 1449.4 | 2760.0 |
| 1242.3 | 2760.0 |
| 1035.3 | 2760.0 |
| 828.2 | 2760.0 |
| 621.2 | 2760.0 |
| 414.1 | 2760.0 |
| 207.1 | 2760.0 |
| 0.0 | 2760.0 |

**Ugrid = 0.95 p.u. Un**

| P [kW] | Qmax [kVar] |
|---|---|
| 4371.1 | 0.0 |
| 4152.6 | 1364.9 |
| 3934.0 | 1905.3 |
| 3715.5 | 2302.6 |
| 3496.9 | 2622.7 |
| 3278.3 | 2760.0 |
| 3059.8 | 2760.0 |
| 2841.2 | 2760.0 |
| 2622.7 | 2760.0 |
| 2404.1 | 2760.0 |
| 2185.6 | 2760.0 |
| 1967.0 | 2760.0 |
| 1748.5 | 2760.0 |
| 1529.9 | 2760.0 |
| 1311.3 | 2760.0 |
| 1092.8 | 2760.0 |
| 874.2 | 2760.0 |
| 655.7 | 2760.0 |
| 437.1 | 2760.0 |
| 218.6 | 2760.0 |
| 0.0 | 2760.0 |

**Ugrid = 1.00 p.u. Un** (also applicable 1.00–1.15 p.u.)

| P [kW] | Qmax [kVar] |
|---|---|
| 4600.0 | 0.0 |
| 4370.0 | 1436.3 |
| 4140.0 | 2005.1 |
| 3910.0 | 2423.2 |
| 3680.0 | 2760.0 |
| 3450.0 | 2760.0 |
| 3220.0 | 2760.0 |
| 2990.0 | 2760.0 |
| 2760.0 | 2760.0 |
| 2530.0 | 2760.0 |
| 2300.0 | 2760.0 |
| 2070.0 | 2760.0 |
| 1840.0 | 2760.0 |
| 1610.0 | 2760.0 |
| 1380.0 | 2760.0 |
| 1150.0 | 2760.0 |
| 920.0 | 2760.0 |
| 690.0 | 2760.0 |
| 460.0 | 2760.0 |
| 230.0 | 2760.0 |
| 0.0 | 2760.0 |

> If additional inverter models are used across the 10-unit fleet, their tables follow
> the identical structure (same column layout) and can be added as additional voltage
> bin sets keyed by inverter type.

---

## 3. Architecture: two-stage clamping

The capability target (from ANRE-compliant control logic) and the physical inverter
limit (from the SMA table) are **separate layers**. Do not merge them into a single
lookup — the ANRE target is what gets tested/certified; the SMA envelope is a hard
safety/physical clamp that must never be exceeded regardless of what the target logic
computes.

```
Q_target        = f_ANRE(P_setpoint, U_measured, mode)   // Stage 1: ANRE PQ_Table (5 tiers, linear interp)
Q_envelope_max  = f_SMA(P_setpoint/N_Online, U_pu)       // Stage 2: FC_SMA_QEnvelope (2D P-U interp)
Q_command       = LIMIT(-Q_envelope_max, Q_target, +Q_envelope_max)
```

> **Stage 2 input note:** Uses `P_setpoint_kW` (FreqResponse output dispatched to inverters) — NOT `P_actual_kW` (grid meter). Reason: P_actual lags during ramps and is unreliable/zero in simulation. P_setpoint reflects what inverters are commanded this cycle.

### 3.1 SMA envelope lookup — interpolation requirements

- **P-axis:** piecewise-linear interpolation between adjacent `Pbin` rows (21 points
  per voltage bin as tabulated). Do not extrapolate beyond the table's P range — clamp
  to the nearest bin edge.
- **U-axis:** only 3 distinct breakpoints exist (0.85, 0.90, 0.95; the 1.00–1.15 bin is
  flat across that entire span). Linear interpolation between 0.85↔0.90 and 0.90↔0.95;
  outside 0.95–1.15, clamp to the 1.00 p.u. curve (per datasheet note, it's valid across
  the whole 1.00–1.15 range).
- **Voltage source:** confirm whether per-inverter terminal voltage is available via
  Modbus, or whether POC/bus voltage (converted to each inverter's per-unit basis) will
  be used as a proxy. Per-inverter voltage is more accurate if available.
- **Output structure:** a function block `FC_PPC_SMA_QEnvelope` (or similar) taking
  `P_actual`, `U_pu`, `InverterType` and returning `Q_max_available` (symmetric ± limit).

### 3.2 Data structure (implemented in SCL)

```
TYPE "UDT_SMA_QRow" VERSION : 0.1
   STRUCT
      P_kW      : Real;
      Qmax_kVar : Real;
   END_STRUCT;
END_TYPE

TYPE "UDT_SMA_QTable" VERSION : 0.1
   STRUCT
      U085 : Array[0..20] of "UDT_SMA_QRow";
      U090 : Array[0..20] of "UDT_SMA_QRow";
      U095 : Array[0..20] of "UDT_SMA_QRow";
      U100 : Array[0..20] of "UDT_SMA_QRow";   // valid 1.00-1.15 p.u.
   END_STRUCT;
END_TYPE
```

Data block `DB_SMA_SC4600UP` (NON_RETAIN constant, `Table : UDT_SMA_QTable`) holds all 84 values (4 bins × 21 rows) from the SMA SC 4600 UP datasheet. Ascending P storage: index 0 = P=0/Qmax=2760, index 20 = Pmax/Qmax=0.

Function `FC_SMA_QEnvelope` (FC, SCL) performs the 2D interpolation: P-axis piecewise-linear scan (21 rows), U-axis linear blend between the two bounding voltage bins. Called from both `FB_PPC_QCapability` (Stage 2 plant-level clamp) and `FC_PPC_ReactiveControl` (Sim_Mode PF→Q clamp per inverter).

---

## 4. Zero-P / Zero-Q handling (Art. 150(2), 152(2)(c))

The SMA table confirms the **inverter is not the limiting factor** at P=0 — full Qmax
(2760 kVar) remains available. The compliance challenge is entirely at the **plant
level**, driven by:

- MV/HV step-up transformer no-load (magnetizing) reactive consumption
- MV collection cable charging capacitance
- Any capacitor banks / filters in the plant

### Required control structure

1. **Capability curve** — P-Q lookup table (§3) collapses to `Qmin = Qmax = 0` at the
   P=0 tier of the *ANRE target* diagram (not the SMA envelope, which stays wide open).
2. **POC compensation term** — added specifically at/near P=0:
   - Fixed feedforward value (transformer no-load Q, derived from nameplate or
     commissioning measurement), and/or
   - Slow POC-feedback trim: `Q_correction = -Q_POC_measured` (integral/slow-PI, not
     fast — this is steady-state balancing, not dynamic grid support)
3. **Tolerance target:** confirm which of the three Art. 152(2)(c) bands applies to
   this plant's actual connection topology (voltage class + busbar vs. line
   connection) — this determines whether the design target is 0.5 MVAr or 0.1 MVAr.
   **Open item — needs plant single-line diagram confirmation.**

---

## 5. SCADA exposure requirements

Per existing SCADA-exposure pattern, the following should be exposed for commissioning
and ongoing operation:

- Active capability curve in use (per-inverter, live Qmax at current P/U)
- Q_target vs. Q_command vs. Q_actual (to visualize clamping events)
- Q_POC_measured and the P=0 compensation term value
- Flag/counter for envelope-clamp events (target Q exceeded SMA physical limit)
- Selected connection-topology tolerance band (0.5 / 0.1 MVAr) as a configured
  parameter, for ISCE traceability

---

## 6. Open items — status

1. **Droop/RampControl wiring** — **RESOLVED.** Droop correction (P response) bypasses RampControl and is applied POST-ramp in FB_PPC_FreqResponse. Q ramp lives in FB_PPC_QCapability (Ramps_Qcmd accumulator, two speeds). Architecture: Step ③ RampControl → Step ④ FreqResponse → Step ⑤ QCapability.

2. **Voltage source for per-inverter envelope lookup** — **RESOLVED (proxy).** U_pu is computed from POC/HV bus measurement: `U_pu = U_meas / U_nom_kV` (U_meas from 110 kV VT AI, U_nom_kV = 110.0). Per-inverter terminal voltage is not available from Modbus in sufficient resolution. POC voltage is the conservative choice (lower voltage → lower envelope) and matches the ANRE regulation voltage reference.

3. **Connection topology / Art. 152(2)(c) tolerance** — **PENDING.** Needs confirmation from single-line diagram: 110 kV connection → applicable tolerance is ≤ 0.5 MVAr. To be confirmed before ISCE Test 10.

4. **Inverter fleet composition** — **RESOLVED.** All 10 units are SMA SC 4600 UP (4600 kW, 4600 kVA). Plant total = 46 MW. Single table in DB_SMA_SC4600UP covers all units. WRtg_kW = 4600.0, Pn_MW = 46.0 set in FC_PPC_InitData and DB39.

5. **U-axis interpolation validation** — **RESOLVED (implemented).** Linear interpolation between 4 voltage bins (0.85/0.90/0.95/1.00 p.u.). U ≤ 0.85 uses U085 only; U > 0.95 uses U100 only (valid 1.00–1.15 per SMA datasheet). Linear interpolation is standard practice for this type of table and matches the continuous taper shape of the SMA data.

6. **ANRE PQ_Table values for ISCE Test 8** — **PENDING.** Default 20000 kVAr at all tiers (non-limiting). Must be replaced with contractual capability limits from grid connection agreement before ISCE Test 8.
