# GNPy Library — Expert Optical Network Planner Function Reference

Hierarchical categories with **goal**, **function**, **requirements**, and **typical uses**.

---

## 1. I/O & Data Loading (`gnpy.tools.json_io`)

| Goal | Function | Requirements | Uses |
|------|----------|--------------|------|
| Load equipment library + configs | `load_equipments_and_configs(equipment_filename, extra_equipment_filenames, extra_config_filenames)` | Path(s) to JSON; optional extra equipment/config lists | Single entry point for EDFA, fiber, ROADM, transceiver, SI, Span definitions |
| Load equipment only | `load_equipment(filename, extra_configs)` | Path to eqpt JSON; optional config dict | When you already have topology and only need equipment |
| Load network topology | `load_network(filename, equipment)` | Path to JSON/XLS/XLSX topology; equipment dict | Build `DiGraph` from file (nodes = elements, edges = connectivity) |
| Save network | `save_network(network, filename)` | `DiGraph`; path | Export designed/raw network for reuse or inspection |
| Load generic JSON | `load_json(filename)` | Path | Sim params, spectrum, any JSON |
| Load GNPy JSON | `load_gnpy_json(filename)` | Path | JSON with GNPy-specific formatting |
| Save JSON | `save_json(obj, filename)` | Dict/list; path | Export results, configs |
| Save GNPy JSON | `save_gnpy_json(obj, filename)` | Dict; path | Export in GNPy format |
| Load service requests | `load_requests(filename, eqpt, bidir, network, network_filename)` | Service file path; equipment; bidir flag; network + filename | Parse service sheet (JSON/XLS/XLSX) into request dict |
| Requests from dict | `requests_from_json(json_data, equipment)` | Request dict from `load_requests`; equipment | List of `PathRequest` objects |
| Load initial spectrum | `load_initial_spectrum(filename)` | Path to spectrum JSON | User-defined mixed-rate spectrum for propagation |
| Load disjunctions | `disjunctions_from_json(json_data)` | Dict with disjunction entries | List of `Disjunction` (link/node diversity) |
| Merge equipment | `merge_equipment(equipment, extra_equipments, extra_configs)` | Main equipment dict; extra equipment dicts; extra config dicts | Combine vendor/pluggable libs with main lib |
| Results to JSON | `results_to_json(pathresults)` | List of `ResultElement` | Export path-request run results |
| Load eqpt + topo from JSON | `load_eqpt_topo_from_json(eqpt, topology, extra_equipments)` | Equipment dict; topology dict; optional extra equipment | Single-call load for API use |
| Find equalisation | `find_equalisation(params, equalization_types)` | Params dict; list of equalization type names | Resolve equalization config from equipment |
| Convert service sheet | `convert_service_sheet(...)` | Service sheet + equipment | Normalize service data for requests |

---

## 2. Network Design & Auto-Design (`gnpy.core.network`)

| Goal | Function | Requirements | Uses |
|------|----------|--------------|------|
| Add missing elements | `add_missing_elements_in_network(network, equipment)` | Network `DiGraph`; equipment dict | Insert EDFAs after ROADMs/fibers, split long fibers |
| Add missing fiber attrs | `add_missing_fiber_attributes(network, equipment)` | Network; equipment | Fill fiber params from library |
| Build network (design) | `build_network(network, equipment, reference_channel, ...)` | Network; equipment; `SpectralInformation` ref channel | Set amplifier gains/VOAs, ROADM ref carrier, fiber input power for one reference |
| Design network | `design_network(reference_channel, network, equipment, set_connector_losses, ...)` | Ref channel; network; equipment; connector flag | Full auto-design: add elements + build_network |
| Span loss | `span_loss(network, node, equipment, ref_power)` | Network; Fiber/Fused node; equipment; ref power | Compute loss of a span (for gain target) |
| Select EDFA | `select_edfa(raman_allowed, gain_target, power_target, edfa_eqpt, uid, ...)` | Booleans; gain/power targets; equipment; node uid | Choose amplifier type from library for a span |
| Set one amplifier | `set_one_amplifier(node, prev_node, next_node, network, equipment, ref_channel, ...)` | EDFA node; prev/next nodes; network; equipment; ref channel | Configure single EDFA (gain, NF, VOA) |
| Set amplifier VOA | `set_amplifier_voa(amp, power_target, power_mode, ...)` | Edfa element; target power; power_mode bool | Set output VOA for power/gain control |
| Add inline amplifier | `add_inline_amplifier(network, fiber)` | Network; Fiber node | Insert EDFA after fiber |
| Add ROADM booster | `add_roadm_booster(network, roadm)` | Network; ROADM node | Add booster amp at ROADM egress |
| Add ROADM preamp | `add_roadm_preamp(network, roadm)` | Network; ROADM node | Add preamp at ROADM ingress |
| Split fiber | `split_fiber(network, fiber, bounds, target_length)` | Network; Fiber; length bounds; target length | Split long fiber into segments (e.g. max 80 km) |
| Add connector loss | `add_connector_loss(network, fibers, default_con_in, ...)` | Network; list of fibers; loss values | Add connector loss to fiber ends |
| Add fiber padding | `add_fiber_padding(network, fibers, padding, equipment)` | Network; fibers; padding length; equipment | Pad short fibers for design |
| Target power at node | `target_power(network, node, ref_power)` | Network; passive node; ref power | Compute target power at fiber/ROADM input |
| Get OMS edge list | `get_oms_edge_list(oms_ingress_node, network)` | ROADM/Transceiver; network | Edges belonging to one OMS (for spectrum) |
| Set ROADM ref carrier | `set_roadm_ref_carrier(roadm, equipment)` | ROADM; equipment | Set reference carrier for ROADM design |
| Set ROADM per-degree targets | `set_roadm_per_degree_targets(roadm, network)` | ROADM; network | Per-degree design bands/targets |
| Set ROADM internal paths | `set_roadm_internal_paths(roadm, network)` | ROADM; network | Internal connectivity for degrees |
| Set fiber input power | `set_fiber_input_power(network, fiber, equipment, pref_ch_db)` | Network; fiber; equipment; ref power | Design fiber launch power |
| Set ROADM input powers | `set_roadm_input_powers(network, roadm, equipment, pref_ch_db)` | Network; ROADM; equipment; ref power | Per-degree input power design |
| EDFA NF from gain | `edfa_nf(gain_target, amp_params)` | Gain; amp params | Noise figure for variable_gain model |
| Estimate Raman gain | `estimate_raman_gain(node, equipment, power_dbm)` | RamanFiber node; equipment; power | Raman gain estimate for design |
| Find first/last node | `find_first_node(network, node)` / `find_last_node(network, node)` | Network; node | Traverse to segment end (for design) |
| Get next/previous node | `get_next_node(node, network)` / `get_previous_node(node, network)` | Node; network | Single step in graph |

---

## 3. Path Computation & Routing (`gnpy.topology.request`)

| Goal | Function | Requirements | Uses |
|------|----------|--------------|------|
| Compute constrained path | `compute_constrained_path(network, req)` | Network; `PathRequest` (source, dest, nodes_list, loose_list) | Shortest/constrained path as list of elements |
| Compute paths with disjunctions | `compute_path_dsjctn(network, equipment, pathreqlist, disjunctions_list)` | Network; equipment; list of PathRequest; list of Disjunction | Paths satisfying link/node diversity |
| Compute path with disjunction (propagate) | `compute_path_with_disjunction(network, equipment, pathreqlist, pathlist, redesign)` | Network; equipment; requests; path list; redesign bool | Run propagation for each path; optional redesign per request |
| Explicit path from node list | `explicit_path(node_list, source, destination, network)` | List of node UIDs; source; dest; network | Build path from explicit ROADM/trx list |
| Propagate on path | `propagate(path, req, equipment)` | Path (element list); PathRequest; equipment | Run signal propagation along path; return receiver SI |
| Propagate and optimize mode | `propagate_and_optimize_mode(path, req, equipment)` | Path; request; equipment | Propagate and pick best transceiver mode |
| Filter SI to path | `filter_si(path, equipment, si)` | Path; equipment; SpectralInformation | Restrict spectrum to path band support |
| Correct JSON route list | `correct_json_route_list(network, pathreqlist)` | Network; list of PathRequest | Fix/validate nodes_list/loose_list from JSON |
| Requests aggregation | `requests_aggregation(pathreqlist, disjlist)` | Requests; disjunctions | Aggregate similar requests for path computation |
| Deduplicate disjunctions | `deduplicate_disjunctions(disjn)` | List of Disjunction | Remove duplicate disjunction entries |
| Check disjoint paths | `isdisjoint(pth1, pth2)` | Two path lists | Whether two paths are link/node disjoint |
| Find reversed path | `find_reversed_path(pth)` | Path list | Reverse path order (for bidir) |
| Check path containment | `ispart(ptha, pthb)` | Two paths | Whether ptha is subpath of pthb |
| Spectrum slot vs bandwidth | `compute_spectrum_slot_vs_bandwidth(bandwidth, spacing, bit_rate, slot_width)` | Bandwidth; spacing; bit rate; grid | Slots required for request |
| Find elements common range | `find_elements_common_range(el_list, equipment)` | Element list; equipment | Common freq range for path |
| Is adjacent OMS | `is_adjacent(oms1, oms2)` | Two OMS objects | Adjacency for spectrum continuity |
| JSON to CSV (results) | `jsontocsv(json_data, equipment, fileout)` | Result JSON; equipment; file handle | Export path results to CSV |
| Read property from path metric | `read_property(path_metric, metric_type)` | Path metric structure; type | Extract OSNR/GSNR etc. from response |
| Penalty / OSNR message | `penalty_msg(receiver, msg, min_ind, required_osnr, system_margins)` | Receiver element; message; index; OSNR; margins | User-facing penalty/OSNR message |
| Get penalty from receiver | `get_penalty_from_receiver(receiver, impairment)` | Receiver; impairment name | Penalty value for impairment |

---

## 4. Spectrum Assignment (`gnpy.topology.spectrum_assignment`)

| Goal | Function | Requirements | Uses |
|------|----------|--------------|------|
| Build OMS list | `build_oms_list(network, equipment)` | Network; equipment | List of OMS (optical multiplex sections) for whole network |
| Assign spectrum to paths | `pth_assign_spectrum(pths, rqs, oms_list, reversed_pths, policy)` | Path lists; PathRequests; OMS list; reversed paths; policy (e.g. FIRST_FIT) | Assign (n, m) slots to each request |
| Frequency to slot index | `frequency_to_n(freq, grid)` | Frequency Hz; grid (default 12.5e9) | ITU-T n value |
| Slot index to frequency | `nvalue_to_frequency(nvalue, grid)` | n; grid | Center frequency from n |
| N,M to slots | `mvalue_to_slots(nvalue, mvalue)` | n; m | Start/stop slot indices |
| Slots to N,M | `slots_to_m(startn, stopn)` | Start/stop slot indices | (n, m) representation |
| N,M to freq range | `m_to_freq(nvalue, mvalue, grid)` | n; m; grid | (f_min, f_max) in Hz |
| Align OMS grids | `align_grids(oms_list)` | List of OMS | Align grid across OMS |
| Find network freq range | `find_network_freq_range(network)` | Network | Global f_min, f_max |
| Create OMS bitmap | `create_oms_bitmap(oms, equipment, f_min, f_max, ...)` | OMS; equipment; freq range | Occupancy bitmap for OMS |
| Build path OMS id list | `build_path_oms_id_list(pth, oms_list)` | Path; OMS list | OMS IDs traversed by path |
| Aggregate OMS bitmap | `aggregate_oms_bitmap(path_oms, oms_list)` | Path OMS IDs; OMS list | Combined bitmap along path |
| Spectrum selection | `spectrum_selection(test_oms, requested_m, requested_n, ...)` | OMS; slots; optional n; policy | Find candidate (n, m) block |
| Determine slot numbers | `determine_slot_numbers(test_oms, requested_n, required_m, per_channel_m)` | OMS; n; m; per-channel m | Slot count for request |
| Select candidate | `select_candidate(candidates, policy)` | List of (n, m, ...); policy | Pick one candidate (e.g. first_fit) |
| Compute N,M for request | `compute_n_m(required_m, rq, path_oms, oms_list, per_channel_m, ...)` | Required slots; PathRequest; path OMS; OMS list; per-channel m | (n, m) for request on path |
| Reversed OMS | `reversed_oms(oms_list)` | OMS list | OMS list for reverse direction |
| Bitmap sum | `bitmap_sum(band1, band2)` | Two bitmap lists | Combined occupancy |

---

## 5. Signal & Spectral Information (`gnpy.core.info`)

| Goal | Function | Requirements | Uses |
|------|----------|--------------|------|
| Create SI from params | `create_input_spectral_information(f_min, f_max, roll_off, baud_rate, spacing, tx_osnr, tx_power, ...)` | SI params (freq range, roll-off, baud, spacing, OSNR, power) | Reference or default spectrum |
| Create arbitrary SI | `create_arbitrary_spectral_information(frequency, baud_rate, roll_off, tx_osnr, tx_power, ...)` | Arrays/lists for freq, baud, etc. | Mixed-rate or custom channel set |
| Carriers to SI | `carriers_to_spectral_information(initial_spectrum, equipment, ...)` | Dict of Carrier; equipment | User spectrum (e.g. from JSON) to SpectralInformation |
| Select channels | `select_channels(spectrum, select)` | SpectralInformation; boolean array | Subset of channels |
| In band check | `is_in_band(frequency, slot_width, band)` | Freq array; slot width; band dict | Which channels fall in band |
| Demuxed SI | `demuxed_spectral_information(input_si, band)` | SI; band | SI after demux to band |
| Muxed SI | `muxed_spectral_information(input_si_list)` | List of SpectralInformation | Combine several SI into one |

---

## 6. Propagation & Physics (`gnpy.core.science_utils`)

| Goal | Function | Requirements | Uses |
|------|----------|--------------|------|
| Raised cosine | `raised_cosine(frequency, channel_frequency, channel_baud_rate, channel_roll_off)` | Freq array; channel freq; baud; roll-off | Channel shape for NLI/OSNR |
| Raman solver | `RamanSolver` (class) | Fiber params; pump config; sim params | Raman amplification profile |
| NLI solver | `NliSolver` (class) | Fiber; channel plan; sim params | NLI noise (GN model) |
| Stimulated Raman Scattering | `StimulatedRamanScattering` (class) | Fiber coefficients | SRS power transfer |
| NF model estimate | `estimate_nf_model(type_variety, gain_min, gain_max, nf_min, nf_max)` | EDFA type; gain/NF range | NF vs gain for variable_gain |

---

## 7. High-Level Workflows (`gnpy.tools.worker_utils`)

| Goal | Function | Requirements | Uses |
|------|----------|--------------|------|
| Design network for a service | `designed_network(equipment, network, source, destination, nodes_list, loose_list, initial_spectrum, no_insert_edfas, args_power, service_req)` | Equipment; network; optional source/dest/node list/loose/spectrum; no_insert_edfas; power; optional PathRequest | Add missing elements + build_network; return (network, req, ref_req) |
| Run transmission simulation | `transmission_simulation(equipment, network, req, ref_req)` | Equipment; designed network; PathRequest to propagate; ref PathRequest used for design | Propagate; optional power sweep; return path, propagations, powers_dbm, infos |
| Run full planning | `planning(network, equipment, data, redesign, user_policy)` | Network; equipment; service data dict; redesign bool; policy (e.g. FIRST_FIT) | Path computation + disjunctions + spectrum assignment + propagation; return OMS list, paths, requests, disjunctions, result list |
| Check request path IDs | `check_request_path_ids(rqs)` | List of PathRequest | Uniqueness of request_id |

---

## 8. CLI & Examples (`gnpy.tools.cli_examples`)

| Goal | Function | Requirements | Uses |
|------|----------|--------------|------|
| Single-path transmission | `transmission_main_example(args)` | CLI args (topology, source, dest, path, service, equipment, etc.) | Full pipeline: load → design → propagate → print/plot/save |
| Batch path requests | `path_requests_run(args)` | CLI args (topology, service file, equipment, output, etc.) | Load → planning() → table + optional JSON/CSV |
| Load common data | `load_common_data(equipment_filename, extra_equipment_filenames, extra_config_filenames, topology_filename, simulation_filename, save_raw_network_filename)` | Paths for equipment, topology, sim, optional save | Single place to load equipment + network + sim params; exit on error |
| Show example data dir | `show_example_data_dir()` | None | Print example-data path |

---

## 9. Excel / Conversion (`gnpy.tools.convert`, `service_sheet`)

| Goal | Function | Requirements | Uses |
|------|----------|--------------|------|
| XLS/XLSX to JSON | `xls_to_json_data(input_filename, filter_region)` | Path to Excel; optional region filter | Parse topology Excel to dict |
| Convert file | `convert_file(input_filename, filter_region, output_json_file_name)` | Input path; optional region; output path | Excel → JSON file |
| Parse Excel | `parse_excel(input_filename)` | Path | Return nodes, links, eqpt, roadms |
| Sanity check | `sanity_check(nodes, links, ...)` | Parsed nodes/links | Validate topology data |
| Correspondence names | `corresp_names(input_filename, network)` | Excel path; network DiGraph | Map Excel names to network nodes |
| Read service sheet | `read_service_sheet(...)` (service_sheet) | Service Excel path; equipment; network | Parse service requests from Excel |
| Parse service sheet | `parse_service_sheet(service_sheet, is_xlsx)` | Sheet; format flag | Yield Request objects |
| Correct XLS route list | `correct_xls_route_list(network_filename, network, ...)` | Topology path; network; requests | Fix route list from Excel |

---

## 10. Plotting (`gnpy.tools.plots`)

| Goal | Function | Requirements | Uses |
|------|----------|--------------|------|
| Plot baseline network | `plot_baseline(network)` | Network DiGraph (nodes with .lng, .lat) | Matplotlib: network with transceiver labels |
| Plot results (path highlight) | `plot_results(network, path, source, destination)` | Network; path (element list); source/dest nodes | Matplotlib: network with path in red + hover info |

---

## 11. Equipment & Parameters (`gnpy.core.equipment`, `gnpy.core.parameters`)

| Goal | Function | Requirements | Uses |
|------|----------|--------------|------|
| Transceiver mode params | `trx_mode_params(equipment, trx_type_variety, trx_mode, error_message)` | Equipment; transceiver type; mode name; optional error flag | Baud rate, OSNR, penalties, cost, etc. for a mode |
| Find amplifier type variety | `find_type_variety(amps, equipment)` | List of amp names; equipment | Resolve to type_variety from library |
| Find type varieties (multi) | `find_type_varieties(amps, equipment)` | List of amp names; equipment | List of type_variety lists |
| SimParams | `SimParams.set_params(sim_params)` (parameters) | Dict of sim params (Raman, NLI, etc.) | Set global simulation parameters |

---

## 12. Utilities (`gnpy.core.utils`)

| Goal | Function | Requirements | Uses |
|------|----------|--------------|------|
| Linear to dB | `lin2db(value)` | Linear power/ratio | dB value |
| dB to linear | `db2lin(value)` | dB value | Linear ratio |
| Watt to dBm | `watt2dbm(value)` | Power in W | Power in dBm |
| dBm to Watt | `dbm2watt(value)` | Power in dBm | Power in W |
| PSD to power dBm | `psd2powerdbm(psd_mwperghz, baudrate_baud)` | PSD; baud rate | Channel power in dBm |
| Power dBm to PSD | `power_dbm_to_psd_mw_ghz(power_dbm, baudrate_baud)` | Power dBm; baud rate | PSD in mW/GHz |
| Automatic channel count | `automatic_nch(f_min, f_max, spacing)` | Freq range; spacing | Number of channels |
| Automatic f_max | `automatic_fmax(f_min, spacing, nch)` | f_min; spacing; nch | f_max for channel plan |
| Per-label average | `per_label_average(values, labels)` | Value array; label array | Average per label (e.g. per format) |
| Pretty summary print | `pretty_summary_print(summary)` | Summary dict | String for console |
| SNR sum | `snr_sum(snr, bw, snr_added, bw_added)` | SNR; bandwidth; added SNR; added BW | Combined SNR (e.g. multi-span) |
| RRC pulse | `rrc(ffs, baud_rate, alpha)` | Freq array; baud; roll-off | Root-raised-cosine shape |

---

## 13. Elements (Classes — use with network nodes)

| Goal | Class | Requirements | Uses |
|------|--------|--------------|------|
| Transceiver | `elements.Transceiver` | uid, params from equipment | Endpoint; holds OSNR, GSNR, penalties |
| ROADM | `elements.Roadm` | uid, params, degrees | Reconfigurable add/drop; per-degree design |
| Fiber | `elements.Fiber` | uid, length, type_variety | SSMF/NZDSF; loss, dispersion, NLI |
| RamanFiber | `elements.RamanFiber` | Fiber + pump config | Raman-amplified span |
| EDFA | `elements.Edfa` | uid, type_variety, params | Inline/booster/preamp |
| Multiband_amplifier | `elements.Multiband_amplifier` | uid, bands, amplifiers | Multi-band site |
| Fused | `elements.Fused` | uid (e.g. fused fiber span) | Passive fusion of spans |
| Location | `elements.Location` | latitude, longitude, city, region | Geo for plotting/naming |

---

## 14. Request & Result Types (`gnpy.topology.request`)

| Goal | Class | Requirements | Uses |
|------|--------|--------------|------|
| Path request | `PathRequest` | source, destination, tsp, mode, spacing, power, path_bandwidth, nodes_list, loose_list, ... | One service to plan/propagate |
| Disjunction | `Disjunction` | request-id-numbers; link-diverse; node-diverse; relaxable | Diversity constraints between requests |
| Result element | `ResultElement` | PathRequest; path; reversed_path | One result (path + request) for export/summary |

---

## Quick Import Reference

```python
# I/O
from gnpy.tools.json_io import (
    load_equipments_and_configs, load_network, save_network,
    load_requests, requests_from_json, load_initial_spectrum,
    load_json, save_json, disjunctions_from_json
)
# Network design
from gnpy.core.network import (
    add_missing_elements_in_network, design_network, build_network
)
# Path & spectrum
from gnpy.topology.request import (
    compute_constrained_path, propagate, compute_path_dsjctn,
    compute_path_with_disjunction, PathRequest
)
from gnpy.topology.spectrum_assignment import build_oms_list, pth_assign_spectrum
# Workflows
from gnpy.tools.worker_utils import designed_network, transmission_simulation, planning
# Info & utils
from gnpy.core.info import create_input_spectral_information, SpectralInformation
from gnpy.core.utils import watt2dbm, dbm2watt, lin2db, automatic_nch
from gnpy.core.equipment import trx_mode_params
# Plotting
from gnpy.tools.plots import plot_baseline, plot_results
# CLI (for full pipelines)
from gnpy.tools.cli_examples import transmission_main_example, path_requests_run
```
