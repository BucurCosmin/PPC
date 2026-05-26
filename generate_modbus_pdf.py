"""Generate Modbus_Comms_Mapping.pdf for SMA Sunny Central PPC project."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

OUTPUT = r"c:\Users\cosmin\OneDrive\WORK\PPC_ENERGY\Modbus_Comms_Mapping.pdf"

# ── Colours ──────────────────────────────────────────────────────────────────
C_BLUE    = colors.HexColor("#1F4E79")
C_LBLUE   = colors.HexColor("#2E75B6")
C_HEADER  = colors.HexColor("#D6E4F0")
C_ALTROW  = colors.HexColor("#F2F7FB")
C_WHITE   = colors.white
C_BLACK   = colors.black
C_YELLOW  = colors.HexColor("#FFF2CC")
C_GREEN   = colors.HexColor("#E2EFDA")
C_ORANGE  = colors.HexColor("#FCE4D6")

PAGE_W, PAGE_H = A4
MARGIN = 1.8 * cm

# ── Styles ────────────────────────────────────────────────────────────────────
base = getSampleStyleSheet()

def style(name, parent="Normal", **kw):
    s = ParagraphStyle(name, parent=base[parent], **kw)
    return s

S_TITLE   = style("DocTitle",  "Normal",  fontSize=20, textColor=C_BLUE,
                  spaceAfter=6, fontName="Helvetica-Bold", alignment=TA_CENTER)
S_SUB     = style("DocSub",    "Normal",  fontSize=11, textColor=C_LBLUE,
                  spaceAfter=2, alignment=TA_CENTER)
S_H1      = style("H1",        "Normal",  fontSize=13, textColor=C_WHITE,
                  fontName="Helvetica-Bold", spaceAfter=6, spaceBefore=14,
                  backColor=C_BLUE, leftIndent=-4, rightIndent=-4,
                  borderPadding=(4, 6, 4, 6))
S_H2      = style("H2",        "Normal",  fontSize=11, textColor=C_BLUE,
                  fontName="Helvetica-Bold", spaceAfter=4, spaceBefore=10,
                  borderPadding=(0, 0, 2, 0))
S_BODY    = style("Body",      "Normal",  fontSize=9,  spaceAfter=4,
                  leading=13)
S_NOTE    = style("Note",      "Normal",  fontSize=8,  textColor=colors.HexColor("#555555"),
                  fontName="Helvetica-Oblique", spaceAfter=4, leading=12)
S_CODE    = style("Code",      "Normal",  fontSize=8,  fontName="Courier",
                  backColor=colors.HexColor("#F5F5F5"), spaceAfter=4,
                  leading=12, leftIndent=12, rightIndent=12,
                  borderPadding=(4, 4, 4, 4))
S_TH      = style("TH",        "Normal",  fontSize=8,  textColor=C_WHITE,
                  fontName="Helvetica-Bold", alignment=TA_CENTER,
                  backColor=C_LBLUE, leading=11)
S_TD      = style("TD",        "Normal",  fontSize=8,  leading=11)
S_TD_C    = style("TDC",       "Normal",  fontSize=8,  leading=11,
                  alignment=TA_CENTER)
S_TD_MONO = style("TDM",       "Normal",  fontSize=8,  fontName="Courier",
                  leading=11)

def th(text): return Paragraph(text, S_TH)
def td(text): return Paragraph(str(text), S_TD)
def tdc(text): return Paragraph(str(text), S_TD_C)
def tdm(text): return Paragraph(str(text), S_TD_MONO)

def make_table(header_row, data_rows, col_widths, alt=True):
    """Build a styled table with coloured header and alternating row shading."""
    table_data = [header_row] + data_rows
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND",  (0, 0), (-1, 0),  C_LBLUE),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  C_WHITE),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("TOPPADDING",  (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0,0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",(0, 0), (-1, -1), 4),
        ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#AAAAAA")),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_ALTROW] if alt else [C_WHITE]),
    ]
    t.setStyle(TableStyle(style_cmds))
    return t

def h1(text):
    return Paragraph(text, S_H1)

def h2(text):
    return Paragraph(text, S_H2)

def body(text):
    return Paragraph(text, S_BODY)

def note(text):
    return Paragraph("<i>" + text + "</i>", S_NOTE)

def code_block(lines):
    text = "<br/>".join(lines)
    return Paragraph(text, S_CODE)

def spacer(h=0.3):
    return Spacer(1, h * cm)

# ── Document content ──────────────────────────────────────────────────────────
story = []

# Title block
story.append(spacer(0.5))
story.append(Paragraph("SMA Sunny Central", S_TITLE))
story.append(Paragraph("Modbus Comms Block — Register Mapping", S_TITLE))
story.append(spacer(0.2))
story.append(Paragraph("Target: PPC_Controller [DB39] &nbsp;|&nbsp; UDT: Inverter_controller", S_SUB))
story.append(Paragraph("Connection: Modbus TCP &nbsp;|&nbsp; Unit ID = 3 (grid management unit)", S_SUB))
story.append(HRFlowable(width="100%", thickness=2, color=C_BLUE))
story.append(spacer(0.4))

# ── Section 1: Conventions ────────────────────────────────────────────────────
story.append(h1("1.  Protocol Conventions"))
story.append(spacer(0.2))

conv_data = [
    [th("Parameter"), th("Value")],
    [td("Modbus variant"),        td("TCP/IP")],
    [td("Unit (Slave) ID"),       td("3")],
    [td("Register bit-width"),    td("32-bit values — each occupies 2 consecutive 16-bit Modbus registers")],
    [td("Address convention"),    td("1-based (register 1 = Modbus address 0x0000)")],
    [td("Write function code"),   td("FC16 — Write Multiple Registers")],
    [td("Read function code"),    td("FC04 — Read Input Registers (measurements)  |  FC03 — Read Holding Registers (writable params)")],
    [td("Endianness"),            td("Big-endian (high word first)")],
    [td("Cycle"),                 td("Read and write every OB30 scan (100 ms)")],
]

story.append(make_table(
    conv_data[0], conv_data[1:],
    col_widths=[5.5*cm, 11*cm]
))
story.append(spacer(0.3))

story.append(h2("Scaling Formats"))
scale_data = [
    [th("Format"), th("Meaning"), th("Example")],
    [tdc("FIX0"), td("Integer, scaling = 1; value is in physical units"), td("WSpt = 500  →  500 kW")],
    [tdc("FIX4"), td("Integer × 10 000; value is a per-unit fraction"),   td("WAval = 8500  →  0.8500 pu  (85 % available)")],
]
story.append(make_table(scale_data[0], scale_data[1:],
    col_widths=[2.5*cm, 8*cm, 6*cm]))
story.append(spacer(0.4))

# ── Section 2: WRITE registers ────────────────────────────────────────────────
story.append(h1("2.  WRITE to SMA Inverter  (PLC → Inverter, FC16)"))
story.append(spacer(0.1))
story.append(body(
    "Each OB30 cycle the comms block reads the UDT fields listed below and "
    "writes them to the corresponding SMA holding registers using FC16."
))
story.append(spacer(0.2))

w_hdr = [th("UDT Field"), th("SMA Register Name"), th("Reg Address"), th("Type"), th("Scaling"), th("ENUM / Notes")]
w_rows = [
    [tdm("OperMode"),   td("InvOpMod"),         tdc("See manual"), tdc("DInt"), tdc("ENUM"),        td("308 = Operation,  303 = Stop")],
    [tdm("(derived)"),  td("GriMng.RemRdy"),     tdc("See manual"), tdc("DInt"), tdc("ENUM"),        td("308 = Ready,  303 = Standby — NOT in UDT; comms block derives from OperMode")],
    [tdm("WMode"),      td("GriMng.WMod"),       tdc("See manual"), tdc("DInt"), tdc("ENUM"),        td("1079 = WCtlCom,  303 = Off")],
    [tdm("WSpt"),       td("GriMng.WNom"),       tdc("See manual"), tdc("DInt"), tdc("FIX0 (kW)"),   td("Active power setpoint in kW (integer)")],
    [tdm("VArMode"),    td("GriMng.VArMod"),     tdc("See manual"), tdc("DInt"), tdc("ENUM"),        td("1072 = VArCtlCom,  1075 = PFCtlCom,  303 = Off")],
    [tdm("VArSpt"),     td("GriMng.VArNom"),     tdc("See manual"), tdc("DInt"), tdc("FIX0 (kVAr)"), td("Reactive power setpoint in kVAr (integer)")],
    [tdm("PFSpt"),      td("GriMng.PFNom"),      tdc("See manual"), tdc("DInt"), tdc("FIX4 (×10000)"), td("9500 = PF 0.950,  10000 = PF 1.000")],
    [tdm("ErrClr"),     td("FltRst"),            tdc("Holding reg 8"), tdc("DInt"), tdc("—"),        td("26 = Acknowledge (one-shot),  0 = idle  — see one-shot rule below")],
]
story.append(make_table(w_hdr, w_rows,
    col_widths=[2.5*cm, 3.2*cm, 2.2*cm, 1.4*cm, 2.2*cm, 5.0*cm]))
story.append(note(
    "Register addresses marked 'See manual' must be confirmed from: "
    "SMA\\SCADA_Modbus_Register_Map_SMA_SunnyCentral_ENUMS_Ramps_RideThrough_PPC_RO.xlsx"
))
story.append(spacer(0.4))

story.append(h2("2a.  Start / Stop Interlock Sequence"))
story.append(body(
    "The SMA inverter enforces a strict write sequence. Writing out of order will be "
    "rejected or cause unexpected behaviour. The comms block MUST derive RemRdy internally "
    "from OperMode and guarantee the following order:"
))
story.append(spacer(0.15))

seq_data = [
    [th("Command"), th("Step"), th("Register written"), th("Value")],
    [tdc("START\n(OperMode → 308)"), tdc("1"), td("GriMng.RemRdy"), tdc("308  (Ready)")],
    [tdc(""),                        tdc("2"), td("InvOpMod"),       tdc("308  (Operation)")],
    [tdc("STOP\n(OperMode → 303)"),  tdc("1"), td("GriMng.RemRdy"), tdc("303  (Standby)")],
    [tdc(""),                        tdc("2"), td("InvOpMod"),       tdc("303  (Stop)")],
]
t = Table(seq_data, colWidths=[3.5*cm, 1.5*cm, 4.5*cm, 3*cm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND",   (0, 0), (-1, 0),  C_LBLUE),
    ("TEXTCOLOR",    (0, 0), (-1, 0),  C_WHITE),
    ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
    ("FONTSIZE",     (0, 0), (-1, -1), 8),
    ("TOPPADDING",   (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
    ("LEFTPADDING",  (0, 0), (-1, -1), 4),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#AAAAAA")),
    ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ("SPAN",         (0, 1), (0, 2)),
    ("SPAN",         (0, 3), (0, 4)),
    ("BACKGROUND",   (0, 1), (-1, 2),  C_GREEN),
    ("BACKGROUND",   (0, 3), (-1, 4),  C_ORANGE),
]))
story.append(t)
story.append(spacer(0.3))

story.append(h2("2b.  ErrClr One-Shot Rule"))
story.append(body(
    "ErrClr in the UDT is set to <b>26</b> for exactly one OB30 scan (100 ms) by the "
    "FaultHandler FC, then returns to 0. The comms block must:"
))
story.append(body("&nbsp;&nbsp;&bull;  Write Holding Register 8 = 26 in the scan where ErrClr &ne; 0."))
story.append(body("&nbsp;&nbsp;&bull;  Write Holding Register 8 = 0 in all other scans."))
story.append(body(
    "Do NOT continuously write 26. The SMA inverter requires a rising edge (0 &rarr; 26) "
    "to acknowledge a fault — repeated writes are ignored."
))
story.append(spacer(0.4))

# ── Section 3: READ registers ─────────────────────────────────────────────────
story.append(h1("3.  READ from SMA Inverter  (Inverter → PLC, FC04)"))
story.append(spacer(0.1))
story.append(body(
    "Each OB30 cycle the comms block reads the following SMA input registers "
    "via FC04 and writes the decoded values into the corresponding UDT fields."
))
story.append(spacer(0.2))

r_hdr = [th("UDT Field"), th("SMA Register Name"), th("Reg Address"), th("Type"), th("Scaling"), th("Derivation / Notes")]
r_rows = [
    [tdm("RemReady"),   td("OpStt"),              tdc("See manual"),    tdc("DInt"), tdc("ENUM"),          td("TRUE when OpStt &isin; {307, 308, 309}.  FALSE otherwise.  See derivation table below.")],
    [tdm("Error"),      td("ErrStt"),             tdc("See manual"),    tdc("DInt"), tdc("ENUM"),          td("TRUE when ErrStt &ne; 307 (307 = Ok).  FALSE = no fault.")],
    [tdm("Wactive"),    td("W"),                  tdc("See manual"),    tdc("DInt"), tdc("FIX0 (kW)"),     td("AC active power output — measured value in kW")],
    [tdm("Qactive"),    td("VAr"),                tdc("See manual"),    tdc("DInt"), tdc("FIX0 (kVAr)"),   td("AC reactive power output — measured value in kVAr")],
    [tdm("WAval"),      td("GriMng.WAval"),       tdc("See manual"),    tdc("DInt"), tdc("FIX4 (pu×10000)"), td("Available active power fraction.  10000 = 100% available.")],
    [tdm("VArAval"),    td("GriMng.VArAval"),     tdc("See manual"),    tdc("DInt"), tdc("FIX4 (pu×10000)"), td("Available reactive power fraction.")],
    [tdm("PwrOffReas"), td("PwrOffReas"),         tdc("Input reg 178"), tdc("DInt"), tdc("ENUM / code"),   td("0 = no event.  Non-zero = disconnection reason code.  21626 = Low Power SetPoint.")],
    [tdm("DrtStt"),     td("DrtStt"),             tdc("See manual"),    tdc("DInt"), tdc("ENUM"),          td("0 = no derating.  Non-zero = derating active (thermal, frequency, etc.)")],
    [tdm("(SCADA log)"),td("ErrNo"),              tdc("Input reg 96"),  tdc("DInt"), tdc("ENUM"),          td("Fault code — NOT stored in UDT.  Log to SCADA when Error = TRUE.")],
]
story.append(make_table(r_hdr, r_rows,
    col_widths=[2.5*cm, 3.2*cm, 2.2*cm, 1.4*cm, 2.4*cm, 4.8*cm]))
story.append(spacer(0.4))

story.append(h2("3a.  RemReady Derivation (from OpStt)"))
story.append(body(
    "SMA does not expose a dedicated remote-ready bit. "
    "The comms block derives RemReady from the OpStt register:"
))
story.append(spacer(0.15))

rr_data = [
    [th("OpStt value"), th("Meaning"),            th("RemReady")],
    [tdc("308"),        td("Operation — producing"),  tdc("TRUE")],
    [tdc("309"),        td("Derating"),               tdc("TRUE")],
    [tdc("307"),        td("Ok (standby / ready)"),   tdc("TRUE")],
    [tdc("303"),        td("Stop"),                   tdc("FALSE")],
    [tdc("35"),         td("Error"),                  tdc("FALSE")],
    [tdc("Other"),      td("Unknown / initialising"), tdc("FALSE")],
]
story.append(make_table(rr_data[0], rr_data[1:],
    col_widths=[3*cm, 6*cm, 3*cm]))
story.append(note(
    "Verify ENUM values against the SMA Modbus manual. "
    "Adjust the table if the actual values differ."
))
story.append(spacer(0.3))

story.append(h2("3b.  Error Derivation (from ErrStt)"))
story.append(body("ErrStt = 307 means 'Ok' (no fault). Map Error as:"))
story.append(code_block(["Error := (ErrStt &lt;&gt; 307)"]))
story.append(spacer(0.4))

# ── Section 4: Per-cycle transaction pseudocode ───────────────────────────────
story.append(PageBreak())
story.append(h1("4.  Per-Cycle Transaction Pseudocode"))
story.append(spacer(0.2))
story.append(h2("4a.  Write Transaction (each OB30 cycle, per inverter)"))
story.append(body(
    "May be batched into a single FC16 call. "
    "Ordering within the frame must respect the interlock sequence in Section 2a."
))
story.append(spacer(0.15))
story.append(code_block([
    "IF ErrClr &lt;&gt; 0 THEN",
    "&nbsp;&nbsp;&nbsp;&nbsp;Write FltRst (reg 8) = ErrClr    // Fault acknowledge one-shot",
    "ELSE",
    "&nbsp;&nbsp;&nbsp;&nbsp;Write FltRst (reg 8) = 0",
    "END_IF",
    "",
    "IF OperMode changed THEN",
    "&nbsp;&nbsp;&nbsp;&nbsp;IF OperMode = 303 THEN              // Stop sequence",
    "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Write GriMng.RemRdy = 303       // Step 1: remove remote permission",
    "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Write InvOpMod = 303            // Step 2: stop",
    "&nbsp;&nbsp;&nbsp;&nbsp;ELSIF OperMode = 308 THEN           // Start sequence",
    "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Write GriMng.RemRdy = 308       // Step 1: grant remote permission",
    "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Write InvOpMod = 308            // Step 2: start",
    "&nbsp;&nbsp;&nbsp;&nbsp;END_IF",
    "END_IF",
    "",
    "Write GriMng.WMod   = WMode       // Active power control mode",
    "Write GriMng.WNom   = WSpt        // Active power setpoint (kW)",
    "Write GriMng.VArMod = VArMode     // Reactive control mode",
    "Write GriMng.VArNom = VArSpt      // Reactive setpoint (kVAr)",
    "Write GriMng.PFNom  = PFSpt       // PF setpoint (x10000)",
]))
story.append(spacer(0.4))

story.append(h2("4b.  Read Transaction (each OB30 cycle, per inverter)"))
story.append(code_block([
    "Read OpStt        &rarr; derive RemReady  (TRUE if OpStt &isin; {307, 308, 309})",
    "Read ErrStt       &rarr; derive Error     (TRUE if ErrStt &lt;&gt; 307)",
    "Read W            &rarr; Wactive  (kW, FIX0)",
    "Read VAr          &rarr; Qactive  (kVAr, FIX0)",
    "Read GriMng.WAval    &rarr; WAval    (pu&times;10000, FIX4)",
    "Read GriMng.VArAval  &rarr; VArAval  (pu&times;10000, FIX4)",
    "Read PwrOffReas (reg 178)  &rarr; PwrOffReas",
    "Read DrtStt              &rarr; DrtStt",
    "// For SCADA alarm logging only (not written to UDT):",
    "Read ErrNo (reg 96)      &rarr; log when Error = TRUE",
]))
story.append(spacer(0.3))
story.append(h2("4c.  Comms Failure Handling"))
story.append(code_block([
    "IF read transaction fails (timeout or exception response) THEN",
    "&nbsp;&nbsp;&nbsp;&nbsp;Set CommError := TRUE for this inverter",
    "&nbsp;&nbsp;&nbsp;&nbsp;// Leave all other UDT fields at their last valid values",
    "&nbsp;&nbsp;&nbsp;&nbsp;// CommError cleared automatically when next successful read completes",
    "END_IF",
]))
story.append(spacer(0.4))

# ── Section 5: Local PLC fields ───────────────────────────────────────────────
story.append(h1("5.  Local PLC Fields — NOT from Modbus"))
story.append(body(
    "These UDT fields are managed entirely within the PLC. "
    "The comms block must NOT overwrite them."
))
story.append(spacer(0.2))

local_data = [
    [th("UDT Field"), th("Type"), th("Source"), th("Description")],
    [tdm("Enabled"),    tdc("Bool"), td("HMI / DB39 operator input"), td("Set TRUE to include inverter in PPC. Set by operator, not by inverter.")],
    [tdm("CommError"),  tdc("Bool"), td("Comms block itself"),         td("Set TRUE if no valid Modbus response within timeout (e.g. 3 consecutive failures). Cleared when comms recover.")],
]
story.append(make_table(local_data[0], local_data[1:],
    col_widths=[2.8*cm, 1.5*cm, 4.5*cm, 7.7*cm]))
story.append(spacer(0.4))

# ── Section 6: DB39 scalars ───────────────────────────────────────────────────
story.append(h1("6.  DB39 Scalar Fields Used by PPC Logic"))
story.append(spacer(0.1))
story.append(body(
    "These fields are in the DB39 PPC_Controller block. "
    "Some are set by SCADA or HMI (inputs to PPC); others are written by the PPC FBs for HMI display."
))
story.append(spacer(0.2))

story.append(h2("Set by SCADA / HMI (inputs to PPC)"))
inp_data = [
    [th("DB39 Field"), th("Type"), th("Description"), th("Source")],
    [tdm("START_CONTROLLER"), tdc("Bool"), td("Maps to EN_PPC FB input — master enable"),                 td("HMI")],
    [tdm("Targets_P"),        tdc("Real"), td("Active power setpoint from SCADA (kW)"),                   td("SCADA (REMOTE) / HMI (LOCAL)")],
    [tdm("Targets_Q"),        tdc("Real"), td("Reactive power setpoint (kVAr)"),                          td("SCADA / HMI")],
    [tdm("Targets_PF"),       tdc("Real"), td("Power factor setpoint"),                                   td("SCADA / HMI")],
    [tdm("P_RampUp"),         tdc("Real"), td("Active power ramp-up rate (kW/s)"),                        td("Engineering / HMI")],
    [tdm("P_RampDown"),       tdc("Real"), td("Active power ramp-down rate (kW/s)"),                      td("Engineering / HMI")],
    [tdm("Q_RampUp"),         tdc("Real"), td("Reactive power ramp-up rate (kVAr/s)"),                    td("Engineering / HMI")],
    [tdm("Q_RampDown"),       tdc("Real"), td("Reactive power ramp-down rate (kVAr/s)"),                  td("Engineering / HMI")],
    [tdm("WRtg_kW"),          tdc("Real"), td("Rated power per inverter (kW) — read from SMA reg 184 at commissioning"), td("Engineering")],
    [tdm("Plant_P_meas"),     tdc("Real"), td("Plant-level active power at PCC (kW) — written by energy meter comms"), td("Meter")],
    [tdm("Plant_Q_meas"),     tdc("Real"), td("Plant-level reactive power at PCC (kVAr)"),                td("Meter")],
]
story.append(make_table(inp_data[0], inp_data[1:],
    col_widths=[3.2*cm, 1.4*cm, 8.0*cm, 3.9*cm]))
story.append(spacer(0.3))

story.append(h2("Written by PPC Logic (outputs for HMI / SCADA)"))
out_data = [
    [th("DB39 Field"), th("Type"), th("Description")],
    [tdm("Plant_Mode"),        tdc("Int"),  td("0 = LOCAL,  1 = REMOTE_IEC,  2 = FALLBACK")],
    [tdm("Plant_N_Online"),    tdc("Int"),  td("Number of inverters currently online")],
    [tdm("Limits_PmaxPlant"),  tdc("Real"), td("Total available active power (kW)")],
    [tdm("Limits_QmaxPlant"),  tdc("Real"), td("Total available reactive power (kVAr)")],
    [tdm("Ramps_Pcmd"),        tdc("Real"), td("Rate-limited active power command (kW)")],
    [tdm("Ramps_Qcmd"),        tdc("Real"), td("Rate-limited reactive power command (kVAr)")],
    [tdm("AnyFault"),          tdc("Bool"), td("TRUE = at least one inverter fault, comm error, or PwrOffReas &ne; 0")],
    [tdm("AnyDerating"),       tdc("Bool"), td("TRUE = at least one healthy inverter is derated")],
    [tdm("FaultMask"),         tdc("Word"), td("Bit i = inverter i has active fault or comm error")],
]
story.append(make_table(out_data[0], out_data[1:],
    col_widths=[3.2*cm, 1.4*cm, 11.9*cm]))
story.append(spacer(0.4))

# ── Section 7: UDT field list ─────────────────────────────────────────────────
story.append(h1("7.  Inverter_controller UDT — Complete Field Reference"))
story.append(spacer(0.1))
story.append(body(
    "All fields of the Inverter_controller UDT and their origin. "
    "The comms block reads/writes only the Modbus-mapped fields; all others must be left untouched."
))
story.append(spacer(0.2))

udt_data = [
    [th("Field"), th("Type"), th("Direction"), th("Origin")],
    [tdm("Enabled"),    tdc("Bool"), tdc("PLC &rarr; UDT"), td("HMI operator input — include in PPC")],
    [tdm("RemReady"),   tdc("Bool"), tdc("Modbus &rarr; UDT"), td("Derived from OpStt register (FC04)")],
    [tdm("Error"),      tdc("Bool"), tdc("Modbus &rarr; UDT"), td("Derived from ErrStt register (FC04)")],
    [tdm("CommError"),  tdc("Bool"), tdc("Comms block"), td("Set by comms block on timeout/failure")],
    [tdm("OperMode"),   tdc("DInt"), tdc("UDT &rarr; Modbus"), td("Written by FaultHandler FC; maps to InvOpMod + RemRdy (FC16)")],
    [tdm("WMode"),      tdc("DInt"), tdc("UDT &rarr; Modbus"), td("Written by PowerDistribution FC; maps to GriMng.WMod (FC16)")],
    [tdm("WSpt"),       tdc("DInt"), tdc("UDT &rarr; Modbus"), td("Written by PowerDistribution FC; maps to GriMng.WNom (FC16)")],
    [tdm("VArMode"),    tdc("DInt"), tdc("UDT &rarr; Modbus"), td("Written by ReactiveControl FC; maps to GriMng.VArMod (FC16)")],
    [tdm("VArSpt"),     tdc("DInt"), tdc("UDT &rarr; Modbus"), td("Written by ReactiveControl FC; maps to GriMng.VArNom (FC16)")],
    [tdm("PFSpt"),      tdc("DInt"), tdc("UDT &rarr; Modbus"), td("Written by ReactiveControl FC; maps to GriMng.PFNom (FC16)")],
    [tdm("ErrClr"),     tdc("DInt"), tdc("UDT &rarr; Modbus"), td("Written by FaultHandler FC; maps to FltRst reg 8 (FC16) — one-shot")],
    [tdm("Wactive"),    tdc("DInt"), tdc("Modbus &rarr; UDT"), td("AC active power output; maps to W register (FC04)")],
    [tdm("Qactive"),    tdc("DInt"), tdc("Modbus &rarr; UDT"), td("AC reactive output; maps to VAr register (FC04)")],
    [tdm("WAval"),      tdc("DInt"), tdc("Modbus &rarr; UDT"), td("Available active power fraction (FIX4); maps to GriMng.WAval (FC04)")],
    [tdm("VArAval"),    tdc("DInt"), tdc("Modbus &rarr; UDT"), td("Available reactive fraction (FIX4); maps to GriMng.VArAval (FC04)")],
    [tdm("PwrOffReas"), tdc("DInt"), tdc("Modbus &rarr; UDT"), td("Disconnection reason code; maps to reg 178 (FC04).  0 = normal.")],
    [tdm("DrtStt"),     tdc("DInt"), tdc("Modbus &rarr; UDT"), td("Derating status; 0 = none active.  FC04.")],
]
story.append(make_table(udt_data[0], udt_data[1:],
    col_widths=[2.8*cm, 1.5*cm, 3.0*cm, 9.2*cm]))
story.append(note(
    "ErrClr : DInt must be added to the Inverter_controller UDT in TIA Portal if not already present."
))
story.append(spacer(0.4))

# ── Footer note ───────────────────────────────────────────────────────────────
story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE))
story.append(spacer(0.2))
story.append(note(
    "Register addresses marked 'See manual' must be confirmed from: "
    "SMA\\SCADA_Modbus_Register_Map_SMA_SunnyCentral_ENUMS_Ramps_RideThrough_PPC_RO.xlsx"
))
story.append(note(
    "Document generated from PPC_ENERGY project.  "
    "For SCL source code see FB_PPC_Controller.scl and associated FCs."
))

# ── Build PDF ─────────────────────────────────────────────────────────────────
doc = SimpleDocTemplate(
    OUTPUT,
    pagesize=A4,
    rightMargin=MARGIN,
    leftMargin=MARGIN,
    topMargin=MARGIN,
    bottomMargin=MARGIN,
)
doc.build(story)
print(f"PDF written to: {OUTPUT}")
