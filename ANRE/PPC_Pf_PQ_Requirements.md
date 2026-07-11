# PPC Tandarei — P-f Droop and P-Q Capability: Programming Requirements

**Source standards:** Ordinul ANRE 51/23.04.2019 (Anexa 12, tabel 12.1) constrained by Ordinul ANRE 60/2024. Test plan: ISCE program de probe, categorie D, 02.05.2026–18.05.2026.

**Scope:** two new function blocks, `FC_PPC_FreqResponse` (P-f droop, RFA) and `FC_PPC_QCapability` (P-Q + U loop), that sit between the plant-level setpoint (currently produced by your ramp control) and the per-inverter Modbus dispatch (10x SMA inverters). Existing `FC_PPC_RampControl` stays as the final ramp-limiting stage downstream of both.

---

## 1. Signal interface (per ISCE test rig — must match exactly)

The test bench injects/reads these as 4–20 mA analog, sample rate 0.5 s. Your PLC must expose equivalent analog channels for the acquisition system, and internally use engineering units.

| Signal | Direction | Notes |
|---|---|---|
| Frecventa sistem [Hz] | Input | **During tests this must be override-able**: ISCE's frequency generator drives an analog input −20 mA…+20 mA mapped to 47.5–52.0 Hz. The plant's frequency response logic must consume *this* input, not the grid-measured frequency, whenever the override is active. |
| Putere activa [MW] | Output (measured) | Plant-level actual P |
| Putere reactiva [MVAr] | Output (measured) | Plant-level actual Q |
| Tensiune_MT [kV] | Output (measured) | MV busbar voltage |
| P.consemn [MW] | Output (echo) | Active power setpoint actually applied |
| Q.consemn [MVAr] | Output (echo) | Reactive power setpoint actually applied |
| U.consemn [kV] | Output (echo) | Voltage setpoint actually applied |
| Putere disponibila [MW] | Output | Plant available power (irradiance-limited), needed for Pmax_disp |

**Design implication:** add a `Frequency_Source_Sel` (real vs. simulated/test) and a `Freq_Test_Override : REAL` input, both exposed to SCADA so the commissioning team can switch during the ISCE campaign without a code change.

---

## 2. FC_PPC_FreqResponse (P-f droop / RFA)

### 2.1 Required interface

```
FUNCTION_BLOCK FB_PPC_FreqResponse
VAR_INPUT
    f_meas          : REAL;   // Hz, from selected source (real or test)
    f_nom            : REAL;   // 50.0
    Droop_OF_pct     : REAL;   // %, over-frequency droop (Art. 114-115), ISCE test at 8.0
    Droop_UF_pct     : REAL;   // %, under-frequency droop (Art. 118-120), ISCE test at 10.0
    DeadBand_mHz     : REAL;   // configurable, default 200; must support 0 for Art.117 fine-response sub-test
    P_setpoint_ext    : REAL;   // MW, upstream P.consemn (from AGC/dispatch or manual)
    Pmin_stab         : REAL;   // MW, beneficiary-provided (Note 1)
    Pmax_disp         : REAL;   // MW, beneficiary-provided, = "Putere disponibila"
    OFRT_Trip_Hz       : REAL;   // 51.5, disconnection threshold (Art.118-120)
    UFRT_Trip_Hz       : REAL;   // lower disconnection threshold if applicable
    Reconnect_Enable   : BOOL;
END_VAR
VAR_OUTPUT
    P_setpoint_final  : REAL;   // MW, after droop correction — feeds FC_PPC_RampControl
    dP_droop          : REAL;   // MW, correction term (diagnostic/SCADA)
    Pmin_active       : REAL;   // MW, dynamic band limit (Note 1 formula)
    Pmax_active       : REAL;   // MW
    Trip_FreqFault    : BOOL;   // f outside 47.5-51.5, disconnect command
    Reconnecting      : BOOL;
    Reconnect_Timer_s : TIME;   // for Art.126-131 reconnection timing test
END_VAR
```

### 2.2 Core droop calculation

Per the note in the test program, the standard's own formula is:

```
|dP| = 2 * Pn * df / bp
```
where `df` in Hz, `bp` = droop in %, `Pn` = plant nominal power (46 MW, 10 × SMA SC 4600 UP). This matches the general droop relation `dP = (Pn/droop)*(df/fn)*100` since `100/f_nom(50) = 2`.

**ANRE specifies different droop values per direction (Ord.51/2019):**
- Art. 114-115 (over-frequency): Droop_OF_pct = 8%
- Art. 118-120 (under-frequency): Droop_UF_pct = 10%

**Implemented as:**

```
df := f_meas - f_nom;

IF ABS(df) <= (DeadBand_mHz / 1000.0) THEN
    dP_droop := 0.0;
ELSIF df > 0.0 THEN
    // Over-frequency (Art. 114-115): reduce P
    dP_droop := -(2.0 * Pn_kW * df) / Droop_OF_pct;
ELSE
    // Under-frequency (Art. 118-120): increase P
    dP_droop := -(2.0 * Pn_kW * df) / Droop_UF_pct;
END_IF;

P_setpoint_final := LIMIT(0, P_setpoint_ext + dP_droop, Pmax_active);
```

Note the dead band is a **hard cutout**, not a soft blend — test Art.117 explicitly runs a 50 mHz step (inside the 200 mHz band) with the dead band forced to 0 to verify the response exists right up to df=0. So `DeadBand_mHz` must be writable from SCADA/engineering, not hardcoded.

### 2.3 Dynamic Pmin/Pmax band (Note 1 of the test program)

```
// Separate headroom per direction — different droops mean different reserves
dP_at_200mHz_OF := (2.0 * Pn_kW * 0.200) / Droop_OF_pct;   // 2300 kW at 8%, 46 MW
dP_at_200mHz_UF := (2.0 * Pn_kW * 0.200) / Droop_UF_pct;   // 1840 kW at 10%
Pmax_active := Pmax_disp  - dP_at_200mHz_OF;   // OF headroom caps ramp output
Pmin_active := Pmin_stab  + dP_at_200mHz_UF;   // UF headroom (diagnostic)
```

This is *not* the same as the runtime `dP_droop` above — it's a static headroom reservation so that when a full ±200 mHz droop response is required, the plant never saturates. Recomputed every cycle so it tracks `Pmax_disp` (irradiance) and droop setting changes.

### 2.4 Test cases to validate against (build these as SCL/PLCSIM test sequences)

| Test | Article | Frequency steps | Droop | Expected behavior |
|---|---|---|---|---|
| 1 | 114–115 | 50→50.2→50.5→51→51.5→back down, step-hold | 8%, 10% | P decreases with over-frequency; verify no action inside dead band; verify reversibility on the way back down |
| 2 | 118–120 | 50→49.8→49.5→49→48.5→48→back to 50 | 8%, 10% | P increases with under-frequency |
| 3 | 117 | 200 mHz and 50 mHz steps, both directions | 8%, 10% | fine-response inside normal band; **dead band forced to 0** for the 50 mHz sub-case |
| 4 | 118–120 | 47.5→...→51.5→50 full sweep | 10% | full-range response; **trip at f_sim > 51.5 Hz**, then verify reconnection sequence |

### 2.5 Trip / reconnect logic (Art. 118–120, cross-referenced with 126–131)

- `Trip_FreqFault` sets when `f_meas > OFRT_Trip_Hz` (51.5 Hz) — command breaker open.
- On `Reconnect_Enable` rising edge (or automatic once `f_meas` returns to normal band), start `Reconnect_Timer_s` at breaker-close command and stop it when plant reaches `Pmax_active` (per available power) — this is exactly what Test 7 (load rejection / auto-reconnect) times. Build this as a shared timestamp mechanism so Test 7 and Test 4's reconnect check use the same instrumentation.

---

## 3. FC_PPC_QCapability (P-Q diagram + voltage loop)

### 3.1 Required interface

```
FUNCTION_BLOCK FB_PPC_QCapability
VAR_INPUT
    P_actual         : REAL;   // MW, current active power operating point
    Pmax             : REAL;   // MW, plant nameplate (48)
    Q_setpoint_ext    : REAL;   // MVAr, external Q command (if in fixed-Q mode)
    U_setpoint_ext    : REAL;   // kV, external U command (if in voltage-droop mode)
    U_meas            : REAL;   // kV, MV busbar measured
    Control_Mode      : INT;    // 0=fixed Q, 1=voltage droop/loop, 2=power factor
    U_Droop_pct       : REAL;
    Q_Ramp_Rate_fast  : REAL;   // MVAr/s or MVAr/min — two speeds required (test 6)
    Q_Ramp_Rate_slow  : REAL;
END_VAR
VAR_OUTPUT
    Q_setpoint_final  : REAL;   // MVAr, feeds per-inverter Q dispatch
    Q_max_inductive   : REAL;   // MVAr, at current P (from capability table)
    Q_max_capacitive  : REAL;
    Q_limited         : BOOL;   // diagnostic: setpoint was clamped
END_VAR
```

### 3.2 P-Q capability table (Art. 147, 152 — Test 8)

The standard requires the capability curve validated at **5 active-power tiers**. Implement as a lookup/interpolation table, parameterized (not hardcoded), since exact MVAr limits depend on your inverter datasheets and grid code category D limits:

```
TYPE UDT_PQ_CapabilityPoint :
STRUCT
    P_pct       : REAL;  // % of Pmax: typically 0, 25, 50, 75, 100
    Q_ind_max   : REAL;  // MVAr, underexcited limit
    Q_cap_max   : REAL;  // MVAr, overexcited limit
END_STRUCT
END_TYPE

// Array of 5 UDT_PQ_CapabilityPoint, linear-interpolated by P_actual/Pmax
```

`Q_max_inductive`/`Q_max_capacitive` at runtime = linear interpolation between the two bracketing table rows for current `P_actual`. Clamp `Q_setpoint_final` to this envelope regardless of control mode — this is the actual "diagrama de capabilitate PQ" the test asks you to raise (Test 8: sweep 0–100% Pmax at 5 tiers, record max admissible Q both directions).

### 3.3 Voltage control loop (Art. 160, 163 — Test 9)

```
IF Control_Mode = 1 THEN
    dU := U_setpoint_ext - U_meas;
    Q_command := dU / (U_Droop_pct/100.0) * Q_nominal_base;   // sign per your grid code convention
ELSE
    Q_command := Q_setpoint_ext;
END_IF;

Q_setpoint_final := LIMIT(-Q_max_inductive, Q_command, Q_max_capacitive);
```

Test 9 sweeps Pmin(0)→Pmax at ≥3 voltage setpoints — make sure the loop is stable (no hunting) across the *whole* P range, including near P=0 where the capability envelope is narrowest.

### 3.4 Q ramp rate limiting (Test 6)

Two independently-testable ramp speeds are required for Q, exactly mirroring what you likely already built for P in `FC_PPC_RampControl`. Reuse that block generically (parameterize the ramp-rate input, don't hardcode P) rather than writing a second ramp limiter — pass `Q_Ramp_Rate_fast`/`slow` through the same rate-limiter FB.

### 3.5 Zero-active-power reactive exchange (Art. 150, 152 — Test 10)

When `P_actual ≈ 0` for ≥30 min, the plant must still be able to source/sink Q on command (verifying inverters don't fully idle/disconnect at P=0). Make sure your inverter enable/standby logic doesn't gate Q dispatch on P>0 — this is a common bug: if inverters go to a "no production" sleep state, Q capability silently disappears. Check `Inverter_controller` UDT state machine for this (relates to the `DrtStt`/derating-state gap already flagged in the PPC review — a P=0 state must not be conflated with "unavailable for Q").

---

## 4. Per-inverter dispatch (10x SMA, Modbus)

Both new FCs output **plant-level** P and Q setpoints. Your existing dispatch logic (splitting plant setpoint across 10 inverters) is the consumer — no change to that split logic should be needed, but confirm:

- Q dispatch respects **per-inverter** capability limits too, not just plant-level (an inverter that's derated or in fault shouldn't be assigned a share of Q it can't deliver — ties back to the missing per-inverter fault diagnostics gap already identified).
- The P=0/Q-active state above must propagate correctly to each inverter's Modbus enable register.

---

## 5. EMS/DMS-SCADA data exchange (Art. 164–165 — Test 12)

Confirm these are exposed to SCADA (matches the ISCE registration list in §1 plus the new diagnostic outputs):

- `Droop_OF_pct` (8%), `Droop_UF_pct` (10%), `DeadBand_mHz`, `Freq_Test_Override`, `Frequency_Source_Sel` — writable, for the ISCE test window
- `dP_droop`, `Trip_FreqFault`, `Reconnecting`, `Reconnect_Timer_s`
- `Q_max_inductive`, `Q_max_capacitive`, `Q_limited`
- `Control_Mode` (Q fixed / U droop / PF) — writable

---

## 6. Open questions — status

1. **Droop sign/direction convention** — **RESOLVED.** Over-frequency → dP < 0 (reduce P), under-frequency → dP > 0 (increase P). Implemented. SMA inverter local droop firmware is not used — PPC controls P directly via WSpt.
2. **Where does `Pmax_disp` come from?** — **RESOLVED.** `PmaxPlant` from FC_PPC_InverterMonitor (sum of `WAval_i × WRtg_kW` for all online inverters). Tracks irradiance in real time.
3. **Q_nominal_base for voltage droop gain** — **RESOLVED.** `QmaxPlant` from FC_PPC_InverterMonitor (sum of `VArAval_i × WRtg_kW`). Adaptive to actual available Q capacity.
4. **Droop bypass of RampControl** — **RESOLVED.** FC_PPC_RampControl applies to external `Cmd_P` only (AGC setpoint changes). FB_PPC_FreqResponse adds droop correction POST-ramp — frequency events are immediate, never rate-limited. Architecture: Step ③ RampControl → Step ④ FreqResponse → P_final_kW to PowerDistribution.
5. **Separate OF/UF droop values (ANRE Art.114-115 vs Art.118-120)** — **RESOLVED.** `Droop_OF_pct = 8.0%` and `Droop_UF_pct = 10.0%` are separate SCADA-writable fields in DB39. Both computed every OB30 cycle — online changes take effect within 100 ms. Dynamic band uses separate OF/UF headroom (2300 kW OF, 1840 kW UF at 46 MW nominal).
