// app.js
const API = (path) => `${location.origin.replace(/:\d+$/, ":" + (window.BACKEND_PORT || "8000"))}${path}`;
window.BACKEND_PORT = undefined; // đặt nếu frontend host khác cổng backend

let donutChart, areaChart, barsChart;
const fmt = new Intl.NumberFormat("en-US", {maximumFractionDigits: 6});
const fmtVol = new Intl.NumberFormat("en-US", {maximumFractionDigits: 2});

function setUpdated() {
    const el = document.querySelector("#last-updated");
    el.textContent = "Updated: " + new Date().toLocaleTimeString();
}

async function fetchJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
}

function ensureChart(ctx, type, data, options) {
    if (type === "doughnut") {
        if (donutChart) donutChart.destroy();
        donutChart = new Chart(ctx, {type, data, options});
    } else if (type === "line") {
        if (areaChart) areaChart.destroy();
        areaChart = new Chart(ctx, {type, data, options});
    } else if (type === "bar") {
        if (barsChart) barsChart.destroy();
        barsChart = new Chart(ctx, {type, data, options});
    }
}

function buildDonut(counts) {
    const labels = Object.keys(counts);
    const values = labels.map(k => counts[k]);
    ensureChart(
        document.getElementById("donut"),
        "doughnut",
        {labels, datasets: [{label: "Count", data: values}]},
        {plugins: {legend: {position: "bottom"}}}
    );
}

function buildArea(series) {
    const labelsSet = new Set();
    Object.values(series).forEach(arr => arr.forEach(([t]) => labelsSet.add(t)));
    const labels = Array.from(labelsSet).sort((a, b) => a - b).map(ms => new Date(ms));

    const ds = Object.keys(series).sort().map((key) => {
        // map mỗi timestamp -> count
        const byTs = new Map(series[key].map(([t, c]) => [t, c]));
        const data = labels.map(d => byTs.get(d.getTime()) || 0);
        return {label: key, data, fill: true, tension: 0.25};
    });

    ensureChart(
        document.getElementById("area"),
        "line",
        {labels, datasets: ds},
        {
            parsing: false,
            scales: {x: {type: "time", time: {unit: "minute"}}},
            plugins: {legend: {position: "bottom"}}
        }
    );
}

function buildBars(items) {
    const labels = items.map(x => x.symbol);
    const values = items.map(x => x.count);
    ensureChart(
        document.getElementById("bars"),
        "bar",
        {labels, datasets: [{label: "Count", data: values}]},
        {plugins: {legend: {display: false}}}
    );
}

function buildTable(rows) {
    const tb = document.getElementById("latest-body");
    tb.innerHTML = "";
    rows.forEach(r => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
      <td>${new Date(r["@timestamp"]).toLocaleString()}</td>
      <td>${r.symbol}</td>
      <td>${r.exchange ?? ""}</td>
      <td>${fmt.format(r.open ?? 0)}</td>
      <td>${fmt.format(r.high ?? 0)}</td>
      <td>${fmt.format(r.low ?? 0)}</td>
      <td>${fmt.format(r.close ?? 0)}</td>
      <td>${fmtVol.format(r.volume ?? 0)}</td>
      <td class="${r.prediction === "UP" ? "up" : r.prediction === "DOWN" ? "down" : ""}">
        ${r.prediction}
      </td>
    `;
        tb.appendChild(tr);
    });
}

async function refreshAll() {
    const min = parseInt(document.getElementById("time-range").value, 10);
    const [counts, ts, top, latest] = await Promise.all([
        fetchJSON(API(`/api/counts?minutes=${min}`)),
        fetchJSON(API(`/api/timeseries?minutes=${min}&interval=1m`)),
        fetchJSON(API(`/api/top-symbols?minutes=${min}&size=10`)),
        fetchJSON(API(`/api/latest?size=100`)),
    ]);
    buildDonut(counts);
    buildArea(ts);
    buildBars(top);
    buildTable(latest);
    setUpdated();
}

function main() {
    document.getElementById("refresh").addEventListener("click", refreshAll);
    document.getElementById("time-range").addEventListener("change", refreshAll);

    let timer = setInterval(refreshAll, 5000);
    const auto = document.getElementById("auto-refresh");
    auto.addEventListener("change", (e) => {
        if (e.target.checked) {
            timer = setInterval(refreshAll, 5000);
        } else {
            clearInterval(timer);
        }
    });

    refreshAll().catch(err => console.error(err));
}

document.addEventListener("DOMContentLoaded", main);