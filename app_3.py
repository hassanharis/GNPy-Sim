"""
GNPy Optical Network Planner — Streamlit App
Load topology & equipment, run transmission/path-request, visualise network with selectable graph and path highlight.
"""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

# Ensure oopt-gnpy is on path when running from GNPy-Simulator
# _APP_DIR = Path(__file__).resolve().parent
# _OOPT_GNPY = _APP_DIR / "oopt-gnpy"
# if _OOPT_GNPY.exists() and str(_OOPT_GNPY) not in sys.path:
 #    sys.path.insert(0, str(_OOPT_GNPY))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from networkx import spring_layout, DiGraph

# GNPy imports (after path fix)
from gnpy.core.elements import Transceiver, Roadm, Fiber, RamanFiber, Edfa, Fused
from gnpy.tools.json_io import (
    load_equipments_and_configs,
    load_network,
    load_json,
    load_requests,
    save_network,
    save_json,
)
from gnpy.tools.worker_utils import designed_network, transmission_simulation, planning
from gnpy.topology.request import PathRequest, ResultElement, compute_constrained_path
from gnpy.core import exceptions
from gnpy.core.utils import watt2dbm

# -----------------------------------------------------------------------------
# Session state init
# -----------------------------------------------------------------------------
def _init_session():
    defaults = {
        "network": None,
        "equipment": None,
        "sim_params": None,
        "service_data": None,
        "topo_filename": None,
        "eqpt_filename": None,
        "last_run_type": None,
        "transmission_result": None,
        "path_request_result": None,
        "selected_source": None,
        "selected_destination": None,
        "path_highlight": None,  # list of node uids (or nodes) for path to highlight
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_session()

# -----------------------------------------------------------------------------
# Helpers: file upload -> Path
# -----------------------------------------------------------------------------
def _upload_to_path(uploaded_file):
    if uploaded_file is None:
        return None
    suffix = Path(uploaded_file.name).suffix
    fd, path = tempfile.mkstemp(suffix=suffix)
    with open(fd, "wb") as f:
        f.write(uploaded_file.getvalue())
    return Path(path)


# -----------------------------------------------------------------------------
# Network graph: build Plotly figure with optional path highlight
# -----------------------------------------------------------------------------
def _node_type(node):
    if isinstance(node, Transceiver):
        return "Transceiver"
    if isinstance(node, Roadm):
        return "ROADM"
    if isinstance(node, (Fiber, RamanFiber)):
        return "Fiber"
    if isinstance(node, Edfa):
        return "EDFA"
    if isinstance(node, Fused):
        return "Fused"
    return "Other"


def _get_positions(network: DiGraph):
    """Return dict node -> (x, y). Use lng/lat if available else spring layout."""
    nodes = list(network.nodes())
    has_loc = all(
        getattr(n, "lng", None) is not None and getattr(n, "lat", None) is not None
        for n in nodes
    )
    if has_loc:
        return {n: (getattr(n, "lng", 0), getattr(n, "lat", 0)) for n in nodes}
    # Undirected for layout
    G = network.to_undirected()
    pos = spring_layout(G, k=1.5, iterations=50)
    return pos


def build_network_figure(network: DiGraph, path_highlight: list | None = None):
    """
    path_highlight: list of nodes (element objects) that form the path to highlight.
    """
    if network is None or network.number_of_nodes() == 0:
        return None
    pos = _get_positions(network)
    path_uids = set()
    if path_highlight:
        for n in path_highlight:
            uid = getattr(n, "uid", None)
            if uid is not None:
                path_uids.add(uid)
            elif isinstance(n, str):
                path_uids.add(n)

    # Edges
    edge_x, edge_y = [], []
    path_edge_x, path_edge_y = [], []
    for u, v in network.edges():
        if u not in pos or v not in pos:
            continue
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        uid_u = getattr(u, "uid", None)
        uid_v = getattr(v, "uid", None)
        on_path = (uid_u in path_uids and uid_v in path_uids) if (uid_u and uid_v) else False
        (path_edge_x if on_path else edge_x).extend([x0, x1, None])
        (path_edge_y if on_path else edge_y).extend([y0, y1, None])

    traces = []
    # Background edges
    if edge_x:
        traces.append(
            go.Scatter(
                x=edge_x, y=edge_y,
                line=dict(width=1, color="#cccccc"),
                hoverinfo="none",
                mode="lines",
                showlegend=False,
            )
        )
    # Path edges (highlighted)
    if path_edge_x:
        traces.append(
            go.Scatter(
                x=path_edge_x, y=path_edge_y,
                line=dict(width=4, color="#e74c3c"),
                hoverinfo="none",
                mode="lines",
                name="Path",
                showlegend=True,
            )
        )

    # Nodes by type; path nodes highlighted
    type_colors = {
        "Transceiver": "#3498db",
        "ROADM": "#9b59b6",
        "Fiber": "#2ecc71",
        "EDFA": "#e67e22",
        "Fused": "#95a5a6",
        "Other": "#7f8c8d",
    }
    for node in network.nodes():
        x, y = pos[node]
        uid = getattr(node, "uid", None) or str(id(node))
        ntype = _node_type(node)
        on_path = uid in path_uids
        color = "#e74c3c" if on_path else type_colors.get(ntype, "#7f8c8d")
        size = 18 if on_path else 12
        name = getattr(node, "location", None)
        city = name.city if name and getattr(name, "city", None) else uid
        traces.append(
            go.Scatter(
                x=[x], y=[y],
                mode="markers+text",
                marker=dict(size=size, color=color, line=dict(width=2, color="white")),
                text=city if isinstance(node, Transceiver) else uid[:20],
                textposition="top center",
                textfont=dict(size=9),
                name=uid,
                hovertext=f"{uid}<br>{ntype}",
                hoverinfo="text",
                showlegend=False,
            )
        )

    fig = go.Figure(data=traces)
    fig.update_layout(
        title="Network topology" + (" (path highlighted)" if path_uids else ""),
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=20, r=20, t=40, b=20),
        height=550,
        plot_bgcolor="rgba(250,250,250,1)",
        clickmode="event",
    )
    return fig


# -----------------------------------------------------------------------------
# Pages
# -----------------------------------------------------------------------------
def page_home():
    st.title("GNPy Optical Network Planner")
    st.caption("Load topology and equipment, run single-path transmission or batch path-request planning, visualise network and results.")

    c1, c2, c3 = st.columns(3)
    with c1:
        topo = st.session_state.get("topo_filename") or "None"
        st.metric("Topology", topo if isinstance(topo, str) and len(topo) < 30 else (str(topo)[:27] + "..."))
    with c2:
        eqpt = st.session_state.get("eqpt_filename") or "None"
        st.metric("Equipment", eqpt if isinstance(eqpt, str) and len(eqpt) < 30 else (str(eqpt)[:27] + "..."))
    with c3:
        last = st.session_state.get("last_run_type") or "—"
        st.metric("Last run", last)

    st.divider()
    if st.button("Go to Load data"):
        st.session_state["page"] = "Load data"
        st.rerun()
    if st.button("Run single-path transmission"):
        st.session_state["page"] = "Single-path transmission"
        st.rerun()
    if st.button("Run path requests"):
        st.session_state["page"] = "Path requests"
        st.rerun()
    if st.button("View results"):
        st.session_state["page"] = "Results & export"
        st.rerun()

    st.markdown("---")
    st.markdown("Learn more: [GNPy docs](https://gnpy.readthedocs.io/) | [GitHub](https://github.com/TelecomInfraProject/oopt-gnpy)")


def page_load_data():
    st.title("Load data")
    st.markdown("Upload topology (JSON/XLS/XLSX), equipment (JSON), and optionally simulation parameters and service file.")

    topo_file = st.file_uploader("Network topology", type=["json", "xls", "xlsx"], key="up_topo")
    eqpt_file = st.file_uploader("Equipment library", type=["json"], key="up_eqpt")
    sim_file = st.file_uploader("Simulation parameters (optional, required for Raman)", type=["json"], key="up_sim")
    service_file = st.file_uploader("Service requests (optional)", type=["json", "xls", "xlsx"], key="up_svc")

    if st.button("Load topology and equipment"):
        if not topo_file or not eqpt_file:
            st.error("Please upload both topology and equipment files.")
        else:
            try:
                topo_path = _upload_to_path(topo_file)
                eqpt_path = _upload_to_path(eqpt_file)
                equipment = load_equipments_and_configs(eqpt_path, [], [])
                network = load_network(topo_path, equipment)
                st.session_state["equipment"] = equipment
                st.session_state["network"] = network
                st.session_state["topo_filename"] = topo_file.name
                st.session_state["eqpt_filename"] = eqpt_file.name
                if topo_path:
                    topo_path.unlink(missing_ok=True)
                if eqpt_path:
                    eqpt_path.unlink(missing_ok=True)
                st.success(f"Loaded topology '{topo_file.name}' and equipment '{eqpt_file.name}'.")
            except Exception as e:
                st.error(f"Load failed: {e}")
                if "EquipmentConfigError" in str(type(e).__name__) or "NetworkTopologyError" in str(type(e).__name__):
                    st.code(str(e))

    if sim_file and st.button("Load simulation parameters"):
        try:
            sim_path = _upload_to_path(sim_file)
            sim_params = load_json(sim_path)
            st.session_state["sim_params"] = sim_params
            if sim_path:
                sim_path.unlink(missing_ok=True)
            st.success("Simulation parameters loaded.")
        except Exception as e:
            st.error(f"Load failed: {e}")

    if service_file and st.button("Load service requests"):
        try:
            svc_path = _upload_to_path(service_file)
            eq = st.session_state.get("equipment")
            net = st.session_state.get("network")
            if not eq or not net:
                st.error("Load topology and equipment first.")
            else:
                data = load_requests(svc_path, eq, bidir=False, network=net, network_filename=svc_path.as_posix())
                st.session_state["service_data"] = data
                if svc_path:
                    svc_path.unlink(missing_ok=True)
                st.success("Service requests loaded.")
        except Exception as e:
            st.error(f"Load failed: {e}")


def page_network_view():
    st.title("Network view")
    network = st.session_state.get("network")
    if network is None:
        st.warning("Load topology and equipment first (Load data page).")
        return

    transceivers = [n for n in network.nodes() if isinstance(n, Transceiver)]
    trx_uids = [n.uid for n in transceivers]
    if not trx_uids:
        st.warning("No transceivers in network.")
    else:
        idx_s = trx_uids.index(st.session_state["selected_source"]) if st.session_state.get("selected_source") in trx_uids else 0
        idx_d = trx_uids.index(st.session_state["selected_destination"]) if st.session_state.get("selected_destination") in trx_uids else (1 if len(trx_uids) > 1 else 0)
        c1, c2 = st.columns(2)
        with c1:
            src = st.selectbox("Source (transceiver)", trx_uids, index=idx_s, key="sel_src")
            st.session_state["selected_source"] = src
        with c2:
            dest = st.selectbox("Destination (transceiver)", trx_uids, index=idx_d, key="sel_dest")
            st.session_state["selected_destination"] = dest

    path_highlight = st.session_state.get("path_highlight")
    fig = build_network_figure(network, path_highlight=path_highlight)
    if fig:
        st.plotly_chart(fig, use_container_width=True)

    st.caption("Select source and destination above; after running a transmission, the computed path is highlighted in red.")


def page_transmission():
    st.title("Single-path transmission")
    network = st.session_state.get("network")
    equipment = st.session_state.get("equipment")
    if network is None or equipment is None:
        st.warning("Load topology and equipment first.")
        return

    transceivers = {n.uid: n for n in network.nodes() if isinstance(n, Transceiver)}
    if len(transceivers) < 2:
        st.error("Network has fewer than two transceivers.")
        return

    trx_list = list(transceivers.keys())
    idx_s = trx_list.index(st.session_state["selected_source"]) if st.session_state.get("selected_source") in trx_list else 0
    idx_d = trx_list.index(st.session_state["selected_destination"]) if st.session_state.get("selected_destination") in trx_list else (1 if len(trx_list) > 1 else 0)
    source_uid = st.selectbox("Source", trx_list, index=idx_s, key="tx_src")
    dest_uid = st.selectbox("Destination", trx_list, index=idx_d, key="tx_dest")
    power_dbm = st.number_input("Reference power (dBm)", value=0.0, step=0.5, key="tx_power")
    no_insert_edfas = st.checkbox("No insert EDFAs", value=False, key="tx_no_edfa")

    if st.button("Run transmission"):
        try:
            source = transceivers[source_uid]
            destination = transceivers[dest_uid]
            sim_params = st.session_state.get("sim_params") or {}
            if sim_params:
                from gnpy.core.parameters import SimParams
                SimParams.set_params(sim_params)
            nodes_list = [dest_uid]
            loose_list = ["STRICT"]
            network, req, ref_req = designed_network(
                equipment, network, source_uid, dest_uid,
                nodes_list=nodes_list, loose_list=loose_list,
                args_power=power_dbm, no_insert_edfas=no_insert_edfas,
            )
            path, propagations, powers_dbm, infos = transmission_simulation(equipment, network, req, ref_req)
            st.session_state["network"] = network
            st.session_state["last_run_type"] = "transmission"
            st.session_state["transmission_result"] = {
                "path": path,
                "propagations": propagations,
                "powers_dbm": powers_dbm,
                "infos": infos,
                "source": source,
                "destination": destination,
                "req": req,
                "ref_req": ref_req,
            }
            st.session_state["path_highlight"] = path
            st.session_state["selected_source"] = source_uid
            st.session_state["selected_destination"] = dest_uid
            final_gsnr = float(infos.snr.mean()) if hasattr(infos, "snr") and infos.snr is not None else None
            st.success(f"Done. Path has {len(path)} elements." + (f" Final GSNR (mean): {final_gsnr:.2f} dB" if final_gsnr is not None else ""))
            
        except Exception as e:
            st.error(f"Run failed: {e}")
            import traceback
            st.code(traceback.format_exc())


def page_path_requests():
    st.title("Path requests (batch)")
    network = st.session_state.get("network")
    equipment = st.session_state.get("equipment")
    service_data = st.session_state.get("service_data")
    if network is None or equipment is None:
        st.warning("Load topology and equipment first.")
        return

    service_upload = st.file_uploader("Service file (or use already loaded)", type=["json", "xls", "xlsx"], key="pr_svc")
    if service_upload:
        try:
            svc_path = _upload_to_path(service_upload)
            data = load_requests(svc_path, equipment, bidir=False, network=network, network_filename=svc_path.as_posix())
            st.session_state["service_data"] = data
            if svc_path:
                svc_path.unlink(missing_ok=True)
            service_data = data
        except Exception as e:
            st.error(f"Load service file: {e}")

    if service_data is None:
        st.warning("Load or upload a service file to run path requests.")
        return

    bidir = st.checkbox("Bidirectional", value=False, key="pr_bidir")
    redesign = st.checkbox("Redesign per request", value=False, key="pr_redesign")
    policy = st.selectbox("Spectrum policy", ["first_fit"], key="pr_policy")

    if st.button("Run path requests"):
        try:
            if st.session_state.get("sim_params"):
                from gnpy.core.parameters import SimParams
                SimParams.set_params(st.session_state["sim_params"])
            oms_list, propagatedpths, reversed_propagatedpths, rqs, dsjn, result = planning(
                network, equipment, service_data, redesign=redesign, user_policy=policy,
            )
            st.session_state["network"] = network
            st.session_state["last_run_type"] = "path_requests"
            st.session_state["path_request_result"] = {
                "oms_list": oms_list,
                "propagatedpths": propagatedpths,
                "reversed_propagatedpths": reversed_propagatedpths,
                "rqs": rqs,
                "dsjn": dsjn,
                "result": result,
            }
            st.session_state["path_highlight"] = None
            st.success(f"Done. {len(result)} requests processed.")
        except Exception as e:
            st.error(f"Run failed: {e}")
            import traceback
            st.code(traceback.format_exc())


def page_results():
    st.title("Results & export")
    last = st.session_state.get("last_run_type")
    if not last:
        st.info("Run a transmission or path-request first.")
        return

    network = st.session_state.get("network")
    equipment = st.session_state.get("equipment")

    if last == "transmission":
        res = st.session_state.get("transmission_result")
        if not res:
            st.warning("No transmission result in session.")
            return
        path = res["path"]
        infos = res.get("infos")
        source = res.get("source")
        destination = res.get("destination")
        st.subheader("Path elements")
        st.write([getattr(n, "uid", str(n)) for n in path])
        propagations = res.get("propagations")
        powers_dbm = res.get("powers_dbm")
        st.markdown(propagations)
        st.markdown(powers_dbm)
        st.markdown(infos)
        if infos is not None and hasattr(infos, "snr") and infos.snr is not None:
            st.metric("Mean GSNR (dB)", f"{float(infos.snr.mean()):.2f}")
        if path and destination is not None and hasattr(path[-1], "snr"):
            st.metric("Final GSNR (0.1 nm, dB)", f"{float(path[-1].snr_01nm.mean()):.2f}")
        if network and equipment:
            buf = io.BytesIO()
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                save_network(network, tmp_path)
                with open(tmp_path, "rb") as f:
                    buf.write(f.read())
            finally:
                Path(tmp_path).unlink(missing_ok=True)
            buf.seek(0)
            st.download_button("Download network (JSON)", buf, file_name="network.json", mime="application/json", key="dl_net_tx")

    elif last == "path_requests":
        res = st.session_state.get("path_request_result")
        if not res:
            st.warning("No path-request result in session.")
            return
        rqs = res["rqs"]
        result = res["result"]
        propagatedpths = res["propagatedpths"]
        header = ["req id", "demand", "GSNR@bw", "GSNR@0.1nm", "mode", "Gbit/s", "N,M or blocking"]
        rows = []
        for i, rq in enumerate(rqs):
            pth = propagatedpths[i] if i < len(propagatedpths) else None
            gsnr_bw = f"{float(pth[-1].snr.mean()):.2f}" if pth and len(pth) and hasattr(pth[-1], "snr") else "-"
            gsnr_01 = f"{float(pth[-1].snr_01nm.mean()):.2f}" if pth and len(pth) and hasattr(pth[-1], "snr_01nm") else "-"
            demand = f"{rq.source} → {rq.destination}"
            mode = getattr(rq, "tsp_mode", "") or "-"
            gbps = f"{rq.path_bandwidth * 1e-9:.1f}" if rq.path_bandwidth else "-"
            nm = getattr(rq, "blocking_reason", "") or f"({getattr(rq, 'N', '-')},{getattr(rq, 'M', '-')})"
            rows.append([str(rq.request_id)[:20], demand, gsnr_bw, gsnr_01, str(mode), gbps, str(nm)])
        df = pd.DataFrame(rows, columns=header)
        st.dataframe(df, use_container_width=True)
        # Option to highlight one path on the network graph
        if propagatedpths:
            path_options = [f"{rqs[i].request_id}: {rqs[i].source} → {rqs[i].destination}" for i in range(len(rqs))]
            sel = st.selectbox("Highlight path on Network view", ["None"] + path_options, key="res_highlight_path")
            if sel != "None":
                idx = path_options.index(sel)
                st.session_state["path_highlight"] = propagatedpths[idx] if idx < len(propagatedpths) else None
            else:
                st.session_state["path_highlight"] = None
        if equipment:
            from gnpy.tools.json_io import results_to_json
            from gnpy.topology.request import jsontocsv
            rev_pths = res.get("reversed_propagatedpths") or [None] * len(rqs)
            result_elements = [
                ResultElement(rqs[i], propagatedpths[i] if i < len(propagatedpths) else [], rev_pths[i] if i < len(rev_pths) else None)
                for i in range(len(rqs))
            ]
            j = results_to_json(result_elements)
            buf_json = io.BytesIO()
            import json
            buf_json.write(json.dumps(j, indent=2).encode())
            buf_json.seek(0)
            st.download_button("Download results (JSON)", buf_json, file_name="path_results.json", mime="application/json", key="dl_json_pr")
            buf_csv = io.BytesIO()
            import io as _io
            fcsv = _io.StringIO()
            try:
                jsontocsv(j, equipment, fcsv)
            except Exception:
                fcsv.write("response-id,source,destination,path_bandwidth,Pass?,mode,Gbit/s\n")
                for i, rq in enumerate(rqs):
                    pth = propagatedpths[i] if i < len(propagatedpths) else []
                    gbps = f"{rq.path_bandwidth * 1e-9:.1f}" if rq.path_bandwidth else ""
                    fcsv.write(f"{rq.request_id},{rq.source},{rq.destination},{gbps},,,{rq.tsp_mode or ''}\n")
            buf_csv.write(fcsv.getvalue().encode())
            buf_csv.seek(0)
            st.download_button("Download results (CSV)", buf_csv, file_name="path_results.csv", mime="text/csv", key="dl_csv_pr")


def page_settings():
    st.title("Settings / About")
    st.markdown("**GNPy Optical Network Planner** — Streamlit app for loading, running, and visualising GNPy simulations.")
    st.markdown("- [GNPy documentation](https://gnpy.readthedocs.io/)")
    st.markdown("- [GitHub](https://github.com/TelecomInfraProject/oopt-gnpy)")


# -----------------------------------------------------------------------------
# Sidebar navigation
# -----------------------------------------------------------------------------
if "page" not in st.session_state:
    st.session_state["page"] = "Home"

PAGES = {
    "Home": page_home,
    "Load data": page_load_data,
    "Network view": page_network_view,
    "Single-path transmission": page_transmission,
    "Path requests": page_path_requests,
    "Results & export": page_results,
    "Settings / About": page_settings,
}

with st.sidebar:
    st.title("Navigation")
    choice = st.radio("Page", list(PAGES.keys()), index=list(PAGES.keys()).index(st.session_state["page"]) if st.session_state["page"] in PAGES else 0)
    st.session_state["page"] = choice

PAGES[st.session_state["page"]]()
