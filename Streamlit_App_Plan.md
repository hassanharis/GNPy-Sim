# GNPy Optical Network Planner — Streamlit App Plan

A Streamlit-based app to **load** topologies and equipment, **run** transmission and path-request simulations, **visualise** the network and chosen path, and **view** results (GSNR, OSNR, power, tables, exports).

---

## 1. App Goals (High Level)

| Goal | Description |
|------|-------------|
| **Load** | Upload or select topology (JSON/XLS/XLSX), equipment (JSON), optional service file and sim params. |
| **Run** | Execute single-path transmission (A→B) or batch path-request planning with chosen options. |
| **Visualise** | Show network graph (nodes/edges), highlight selected path, optional map view. |
| **View results** | Tables (GSNR/OSNR per request, per channel), power along path, summary metrics. |
| **Export** | Download network JSON, results JSON/CSV, and optional plots. |

---

## 2. Suggested Tech Stack

| Layer | Choice | Purpose |
|-------|--------|---------|
| UI | **Streamlit** | Fast prototyping, file upload, sidebar, tabs, tables, plots. |
| Plotting | **Plotly** or **NetworkX + Matplotlib** | Interactive network graph; reuse or wrap `gnpy.tools.plots` logic. |
| Graph viz | **PyVis** or **Plotly** (network graph) | Interactive zoom/pan; color by type (trx, ROADM, fiber, EDFA). |
| Data | **Pandas** | Request/results tables, CSV export. |
| Backend | **GNPy** (existing) | All load, design, path, spectrum, propagation. |
| State | **st.session_state** | Hold loaded network, equipment, last run results, selected path. |

---

## 3. Information Architecture (Pages / Sections)

Use **one multi-page app** with a sidebar for navigation.

```
├── Home (dashboard)
├── Load data
├── Network view
├── Single-path transmission
├── Path requests (batch)
├── Results & export
└── Settings / About
```

---

## 4. Page-by-Page Plan

### 4.1 Home (Dashboard)

| Element | Description |
|--------|-------------|
| **Title** | “GNPy Optical Network Planner” + short tagline. |
| **Status cards** | “Topology loaded” (filename / “None”), “Equipment loaded”, “Last run” (transmission vs path-request, timestamp). |
| **Quick actions** | Buttons: “Go to Load data”, “Run single-path”, “Run path requests”, “View results”. |
| **Short doc** | 2–3 lines: what the app does + link to GNPy docs. |

**Goal:** One-glance status and fast navigation.

---

### 4.2 Load data

| Element | Description |
|--------|-------------|
| **File upload** | `st.file_uploader` for: topology (JSON/XLS/XLSX), equipment (JSON), optional sim params (JSON), optional service file (JSON/XLS/XLSX). |
| **Or paths** | Optional text inputs for paths under a known “example-data” or project root (for dev/preloaded data). |
| **Actions** | “Load topology”, “Load equipment”, “Load services”, “Load all”. |
| **Validation** | On load: call `load_network` / `load_equipments_and_configs` (or `load_equipment`); on error show `st.error` with message. |
| **Session state** | Store `equipment`, `network`, `sim_params`, `service_data` in `st.session_state`. |
| **Optional** | “Save raw network” checkbox → after load call `save_network` and offer download. |

**GNPy used:** `load_equipments_and_configs`, `load_network`, `load_json`, `load_requests`, `save_network`.

**Goal:** Central place to load and validate all inputs; clear errors.

---

### 4.3 Network view

| Element | Description |
|--------|-------------|
| **Prerequisite** | Require `network` in session state; else “Load topology first”. |
| **Node list** | Dropdown or multiselect of transceiver (and optionally ROADM) UIDs from `network.nodes()` filtered by type. |
| **Graph** | Interactive graph: nodes = elements, edges = connectivity. Color by type (Transceiver, ROADM, Fiber, Edfa). Use node coordinates (e.g. `n.lng`, `n.lat`) if present, else layout (e.g. spring). |
| **Selection** | Click or select “Source” and “Destination” transceivers for use in Single-path transmission. |
| **Summary** | Number of nodes by type, number of edges, list of transceivers. |

**GNPy used:** Network from `load_network`; element types from `gnpy.core.elements`; optional `plot_baseline` logic adapted to Plotly/PyVis.

**Goal:** Visual check of topology and choice of A→B for transmission.

---

### 4.4 Single-path transmission

| Element | Description |
|--------|-------------|
| **Prerequisite** | `network` + `equipment` in session state. |
| **Source / Destination** | Two dropdowns populated from transceivers (or pre-filled from Network view). |
| **Path** | Optional: text or multiselect for explicit path (ROADM list); parsed like `--path` (comma or pipe). |
| **Options** | Power (dBm), “No insert EDFAs”, “Save network after design”; optional “User spectrum” file upload. |
| **Run** | Button “Run transmission”. |
| **Logic** | Build `PathRequest`-like spec (source, dest, nodes_list, loose_list from path if given). Call `designed_network` then `transmission_simulation`. Store in session: `path`, `propagations`, `powers_dbm`, `infos`, `source`, `destination`. |
| **Output** | Success message; “View results” link; optional short summary (span count, final GSNR). |

**GNPy used:** `designed_network`, `transmission_simulation`; path parsing similar to `_get_params_from_path`; optional `load_initial_spectrum` if user spectrum provided.

**Goal:** Run one A→B transmission and keep results for Results & Network view.

---

### 4.5 Path requests (batch)

| Element | Description |
|--------|-------------|
| **Prerequisite** | `network`, `equipment`, and service data (from Load data or upload here). |
| **Service input** | Use session `service_data` or `st.file_uploader` for JSON/XLS/XLSX. |
| **Options** | Bidir, Redesign per request, Spectrum policy (e.g. first_fit), “Save network after design”. |
| **Run** | Button “Run path requests”. |
| **Logic** | `load_requests` + `requests_from_json` (if not already in state); `planning(network, equipment, data, redesign, user_policy)`. Store `oms_list`, `propagatedpths`, `reversed_propagatedpths`, `rqs`, `dsjn`, `result`. |
| **Output** | Success message; “View results” link; optional short summary (number satisfied/blocked). |

**GNPy used:** `load_requests`, `requests_from_json`, `planning`, `disjunctions_from_json`, `correct_json_route_list`.

**Goal:** Run batch planning and store results for tables and export.

---

### 4.6 Results & export

| Element | Description |
|--------|-------------|
| **Mode** | Detect last run type from session (single-path vs path-request). |
| **Single-path** | Table: element UIDs along path; optional columns: power in/out, OSNR, GSNR if available. Per-channel table (channel #, freq, power, OSNR ASE, SNR NLI, GSNR) when `infos` and path[-1] available. Plot: power or GSNR vs element index (Plotly line chart). |
| **Path-request** | Table: request id, demand (source → dest), GSNR@BW, GSNR@0.1nm, OSNR@BW, OSNR@0.1nm, mode, Gbit/s, N,M or blocking reason (reuse `path_requests_run` table logic). |
| **Network graph** | For single-path: same graph as Network view but path highlighted (reuse `plot_results` idea in Plotly). For path-request: optional dropdown to pick one request and highlight its path. |
| **Export** | Buttons: “Download network (JSON)”, “Download results (JSON)”, “Download results (CSV)” (use `results_to_json`, `jsontocsv` for path-request). |
| **Plots** | Optional “Download plot” (PNG) for power/GSNR and network figure. |

**GNPy used:** `ResultElement`, `results_to_json`, `jsontocsv`, `save_network`; data from `transmission_simulation` and `planning` stored in session.

**Goal:** One place to inspect and export all run outputs.

---

### 4.7 Settings / About

| Element | Description |
|--------|-------------|
| **Default paths** | Optional config: example-data dir or project root for “Load from path” in Load data. |
| **Logging** | Optional: verbosity (WARNING/INFO/DEBUG) for GNPy. |
| **About** | GNPy version, link to docs, license, app version. |

**Goal:** Minimal config and attribution.

---

## 5. Data Flow (Session State)

Suggested `st.session_state` keys:

| Key | Type | Set in | Used in |
|-----|------|--------|--------|
| `network` | DiGraph | Load data | Network view, Single-path, Path requests, Results |
| `equipment` | dict | Load data | All run + Results |
| `sim_params` | dict | Load data | Single-path (if Raman), Path requests |
| `service_data` | dict | Load data / Path requests | Path requests, Results |
| `last_run_type` | "transmission" \| "path_requests" \| None | Run pages | Results |
| `transmission_result` | dict (path, propagations, powers_dbm, infos, source, dest) | Single-path | Results |
| `path_request_result` | dict (rqs, propagatedpths, reversed_propagatedpths, dsjn, result) | Path requests | Results |
| `selected_source` / `selected_destination` | str (UID) | Network view / Single-path | Single-path, Results |

---

## 6. Error Handling & Validation

| Where | What |
|-------|------|
| Load data | Try/except around GNPy load; map `exceptions.EquipmentConfigError`, `NetworkTopologyError`, `ParametersError` to `st.error`. |
| Single-path | If no transceivers or only one, show message. If path invalid, show “Path could not be resolved”. |
| Path requests | If service file missing or request IDs not unique, show error before calling `planning`. |
| Results | If no run yet, show “Run a transmission or path-request first”. |

---

## 7. Optional Enhancements (Later)

- **Map view:** Plot nodes on a real map (e.g. folium) using `Location` (lat/lon).
- **Compare runs:** Store multiple results (e.g. list of runs) and compare GSNR/OSNR across runs.
- **Power sweep:** For single-path, allow multiple power points and plot GSNR vs power.
- **Service editor:** Simple form to add/edit one request (source, dest, mode, bandwidth) and append to service data.
- **Theming:** Light/dark theme via Streamlit config.

---

## 8. File Structure (Suggested)

```
GNPy-Simulator/
├── app/
│   ├── __init__.py
│   ├── Home.py           # Dashboard
│   ├── Load.py           # Load data
│   ├── NetworkView.py    # Network graph
│   ├── Transmission.py   # Single-path
│   ├── PathRequests.py   # Batch path-request
│   ├── Results.py        # Results & export
│   ├── Settings.py       # Settings / About
│   └── utils.py          # GNPy wrappers, state helpers, graph layout
├── pages/                # If using Streamlit multipage (optional)
│   └── ...
├── streamlit_app.py      # Main entry: sidebar nav + page routing
├── requirements_streamlit.txt
├── GNPy_Function_Reference.md
└── Streamlit_App_Plan.md  # This file
```

---

## 9. requirements_streamlit.txt (Draft)

```
streamlit>=1.28.0
pandas>=1.5.0
plotly>=5.14.0
networkx>=2.8
matplotlib>=3.6.0
openpyxl>=3.0.0
xlrd>=2.0.0
# GNPy (local or from repo)
# -e ../oopt-gnpy  or  gnpy from PyPI if published
```

---

## 10. Summary

| Phase | Deliverable |
|-------|-------------|
| **1** | Load data page: upload topology + equipment, validate with GNPy, store in session. |
| **2** | Network view: draw graph, select source/destination. |
| **3** | Single-path transmission: run `designed_network` + `transmission_simulation`, show short summary. |
| **4** | Results (single-path): table + optional plot + download network/results. |
| **5** | Path-request run + results table + JSON/CSV export. |
| **6** | Home dashboard, Settings/About, polish and error messages. |

This plan gives a clear hierarchy of GNPy functions (see **GNPy_Function_Reference.md**), and a structured Streamlit app to **load**, **run**, **visualise**, and **view/export** results for both single-path and batch path-request workflows.
