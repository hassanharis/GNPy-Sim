# Workflow Guide - GNPy Simulator

## Complete User Workflow

### Step 1️⃣: Equipment Library (Section 1)
```
┌─ Choose Method ─────────────────────────────────┐
│                                                   │
├─ Option A: Upload File                          │
│  Upload custom equipment.json                   │
│                                                   │
└─ Option B: Select Example         ✨ NEW ✨    │
   └─ Default Equipment Library                   │
      └─ Click "Load Example Equipment File"      │
```

### Step 2️⃣: Auto-Design Parameters (Section 2) *(Optional)*
```
┌─ Configure Auto-Design ──────────────────────────┐
│                                                    │
├─ Choose Mode:                                    │
│  ◉ Power Mode           → Set target power      │
│  ◯ Gain Mode            → Set target gain       │
│  ◯ None (Disable)       → Use as-is             │
│                                                    │
├─ Optional: OpenROADM Design                      │
│  ◯ Version 4                                     │
│  ◯ Version 5                                     │
└─ Set parameters (span length, channels, etc)     │
```

### Step 3️⃣: Network Topology (Section 3) ⭐ **KEY STEP**
```
┌─ Load Topology ──────────────────────────────────┐
│                                               │
├─ Option A: Upload File                       │
│  └─ network.json or network.xlsx             │
│                                               │
└─ Option B: Select Example ✨ **FIXED** ✨   │
   ├─ GNPy Mesh Topology (from GitHub)         │
   │  └─ Click "Load Example Topology"         │
   │                                            │
   └─ Generate Options:                        │
      ├─ Generate Linear Topology              │
      │  ├─ Set: Number of nodes               │
      │  ├─ Set: Span length (km)              │
      │  └─ Click "Generate Topology" (ONCE!)  │
      │                                         │
      ├─ Generate Random Network               │
      │  ├─ Set: Number of nodes               │
      │  ├─ Set: Network density               │
      │  └─ Click "Generate Topology" (ONCE!)  │
      │                                         │
      └─ Generate Random National Network      │
         ├─ Set: Number of nodes               │
         ├─ Set: Network density               │
         └─ Click "Generate Topology" (ONCE!)  │
                                                
IMPORTANT: Once you click "Generate Topology",  
you can navigate to other sections WITHOUT     
it regenerating (BUG FIXED ✅)                  
```

### Step 4️⃣: Simulation Parameters (Section 4) *(Optional)*
```
┌─ Configure Simulation ───────────────────────────┐
│                                                   │
├─ Option A: Upload custom parameters             │
│  └─ simulation_params.json                      │
│                                                   │
└─ Option B: Use Defaults                         │
   └─ Click "Use Default Parameters"              │
```

### Step 5️⃣: Services (Section 5) *(Optional)*
```
┌─ Batch Path Requests ────────────────────────────┐
│                                                   │
├─ Upload services file                           │
│  └─ services.json or services.xlsx              │
│                                                   │
├─ Automatic computation starts                   │
│                                                   │
└─ Download responses (JSON/CSV)                  │
```

### Step 6️⃣: Path Configuration (Section 6) ⭐ **MAIN SECTION**
```
┌─ Configure Path Computation ─────────────────────┐
│                                                   │
├─ Basic Settings:                                │
│  ├─ Number of paths: 1-10                       │
│  ├─ ☐ Compute diverse paths                     │
│  └─ ☐ Compute reverse paths                     │
│                                                   │
├─ Node Selection:                                │
│  ├─ Source node:      [Select from dropdown]   │
│  └─ Destination node: [Select from dropdown]   │
│                                                   │
├─ Constraints:                                   │
│  ├─ Include nodes:    [Multi-select]            │
│  └─ Exclude nodes:    [Multi-select]            │
│                                                   │
├─ Transceiver Config:                            │
│  ├─ Type: [Auto/100G/200G/400G]                │
│  ├─ Mode: [Maximize capacity/DP-QPSK/...]      │
│  ├─ Baudrate (Gbaud)                           │
│  ├─ Roll-off                                    │
│  ├─ Tx OSNR (dB)                               │
│  └─ Min OSNR (dB)                              │
│                                                   │
├─ Network Settings:                              │
│  ├─ Reference power (dBm)                       │
│  ├─ Channel spacing (GHz)                       │
│  └─ ROADM loss (dB)                            │
│                                                   │
├─ Power Sweep (Optional):                        │
│  │ ☐ Enable power sweep                        │
│  ├─ Start power (dBm)                          │
│  ├─ Stop power (dBm)                           │
│  └─ Step (dB)                                   │
│                                                   │
└─ ⚡ "Compute and Simulate Paths" button         │
   └─ Blue button (Primary action)                │
```

### Step 7️⃣: Results (Section 7) ⭐ **FINAL SECTION**
```
┌─ Path Analysis ──────────────────────────────────┐
│                                                   │
├─ Select Path: [Dropdown for multiple paths]     │
│                                                   │
├─ Summary Metrics:                               │
│  ├─ Path Length: X km                           │
│  ├─ GSNR: X.XX dB                              │
│  ├─ OSNR: X.XX dB                              │
│  ├─ Feasibility: ✓ Feasible / ✗ Not Feasible   │
│  ├─ Number of Spans: N                         │
│  ├─ Number of EDFAs: N                         │
│  ├─ Total Loss: X.XX dB                        │
│  ├─ CD: X ps/nm                                │
│  ├─ PMD: X.XX ps                               │
│  └─ PDL: X.XX dB                               │
│                                                   │
├─ Details (Click buttons for more):             │
│  ├─ 📊 Detailed Path Information               │
│  ├─ 📈 Signal & Noise Spectra                  │
│  └─ 🗺️ Path on Network Map                     │
│                                                   │
├─ Power Sweep (if enabled):                     │
│  ├─ Interactive graph: GSNR/OSNR vs Power     │
│  └─ 💾 Download Power Sweep Data (CSV)         │
│                                                   │
└─ ✅ Analysis Complete                           │
```

## Quick Reference: Common Tasks

### Task: Load and View GNPy Example
```
Section 3
├─ Right column
├─ Selectbox: "GNPy Mesh Topology"
├─ Click: "📌 View on GitHub"
└─ Click: "Load Example Topology" ✅
```

### Task: Generate a 10-Node Linear Network
```
Section 3
├─ Right column
├─ Selectbox: "Generate Linear Topology"
├─ Slider: Number of nodes → 10
├─ Slider: Span length → 80 km
└─ Click: "Generate Topology" ✅ (ONCE!)
   └─ Now you can go to Section 6!
```

### Task: Compute Path with Custom Parameters
```
Section 6
├─ Select source and destination
├─ Set transceiver: 200G / DP-16QAM
├─ Set ref power: 0 dBm
├─ Enable power sweep (optional)
└─ Click: "Compute and Simulate Paths" ⚡
```

### Task: Analyze Power Sweep Results
```
Section 7
├─ Select: "Power Sweep (if enabled)"
├─ Click: Different points on graph
└─ View: Results for each power level
```

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Rerun app | `R` |
| Clear cache | `C` |
| Stop server | `Ctrl + C` (terminal) |

## Navigation Tips

✅ **DO:**
- Load/generate topology once in Section 3
- Navigate between sections freely after
- Use unique node names for clarity
- Save generated topologies for reuse

❌ **DON'T:**
- Click buttons multiple times rapidly
- Change topology while in Section 6+
- Refresh page during computation (wait for results)

## Examples by Use Case

### 1. Quick Demo (5 min)
```
1. Section 1: Load Default Equipment
2. Section 3: Generate Linear Topology (10 nodes)
3. Section 6: Select any 2 nodes → Compute
4. Section 7: View results
```

### 2. Mesh Network Analysis (10 min)
```
1. Section 1: Load Default Equipment
2. Section 3: Load GNPy Mesh Topology
3. Section 6: Select specific nodes → Compute
4. Section 7: Analyze OSNR/GSNR
```

### 3. Power Optimization (15 min)
```
1. Section 1-3: Setup as above
2. Section 6: Enable power sweep
3. Section 7: View GSNR vs Power graph
4. Section 7: Download CSV results
```

### 4. Batch Processing (varies)
```
1. Section 1-3: Setup topology
2. Section 5: Upload services.json
3. Results compute automatically
4. Download all path responses
```

---

**Status**: ✅ Workflow bug fixed! No more unexpected topology regeneration.
