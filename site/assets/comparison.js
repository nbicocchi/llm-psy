/* Local, dependency-free views of immutable exported observations. */
(() => {
  "use strict";
  const hasScore = cell => Boolean(cell && Number.isFinite(cell.mean) && cell.n > 0);
  const position = (value, min, max) => 100 * (value - min) / (max - min);
  const selectRows = (rows, family, query, ids) => rows.filter(row =>
    (!family || row.family === family) && row.model.toLowerCase().includes(query.toLowerCase()) &&
    (!ids.length || ids.includes(row.id)));
  const pairs = (rows, x, y) => rows.filter(row => hasScore(row.cells[x]) && hasScore(row.cells[y]));
  if (typeof module !== "undefined") module.exports = { hasScore, position, selectRows, pairs };
  if (typeof document === "undefined") return;
  const payload = document.getElementById("comparison-data");
  if (!payload) return;
  const data = JSON.parse(payload.textContent);
  const app = document.getElementById("comparison-app");
  const byId = id => document.getElementById(id);
  const format = value => Number.isFinite(value) ? String(Number(value.toFixed(3))) : "—";
  const node = (tag, text, className) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  const svgNode = (tag, attributes, text) => {
    const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const palette = ["#17654d", "#8654a0", "#b34f23", "#246ea5", "#997000", "#a53e64", "#486844", "#5356aa", "#765645", "#187e83"];
  const families = [...new Set(data.cohorts.flatMap(group => group.rows.map(row => row.family)))].sort();
  const color = row => palette[families.indexOf(row.family) % palette.length];
  const rowLabel = row => `${row.model} · ${row.mode} · ${row.digest.slice(0, 8)}`;
  const coverage = cell => cell ? `${cell.n}/${cell.planned} complete` : "No recorded run";
  const cellLabel = cell => hasScore(cell) ? `${format(cell.mean)} · ${coverage(cell)}` : cell ? `No complete repetition · ${coverage(cell)}` : "No recorded run";
  const options = (select, entries, selected) => {
    select.replaceChildren();
    entries.forEach(([value, text]) => {
      const option = node("option", text);
      option.value = value;
      select.append(option);
    });
    if (entries.some(([value]) => value === selected)) select.value = selected;
  };
  const cohort = () => data.cohorts.find(group => group.id === byId("cohort-select").value);
  const rows = () => selectRows(cohort().rows, byId("family-select").value, byId("comparison-search").value,
    [...byId("model-select").selectedOptions].map(option => option.value));
  const column = id => cohort().columns.find(item => item.id === id);
  const profileLink = row => {
    const link = node("a", row.model);
    link.href = `${app.dataset.baseurl || ""}${row.url}`;
    return link;
  };
  function table(headers, values) {
    const result = node("table");
    const head = node("thead");
    const heading = node("tr");
    headers.forEach(text => { const th = node("th", text); th.scope = "col"; heading.append(th); });
    head.append(heading);
    result.append(head);
    const body = node("tbody");
    values.forEach(cells => {
      const tr = node("tr");
      cells.forEach((text, index) => {
        const cell = node(index === 0 ? "th" : "td", text);
        if (index === 0) cell.scope = "row";
        tr.append(cell);
      });
      body.append(tr);
    });
    result.append(body);
    return result;
  }
  function inspect(row, scale, cell) {
    const host = byId("cell-detail");
    host.replaceChildren(node("h3", `${row.model} / ${scale.trait}`));
    host.append(node("p", `${scale.label} · ${scale.aggregation} scoring · range ${scale.min}–${scale.max}`));
    host.append(node("p", `${cellLabel(cell)} · SD ${format(cell && cell.sd)}`));
    host.append(node("p", rowLabel(row), "coverage"));
    host.append(node("p", `Protocol: ${JSON.stringify(scale.protocol)} · Questionnaire SHA-256: ${scale.questionnaire_hash}`, "coverage"));
    if (cell) {
      host.append(node("p", `Complete repetitions: ${cell.repetitions.map(rep => `#${rep.repetition}: ${format(rep.score)}`).join("; ") || "None"}`));
      host.append(node("p", `Run coverage: ${cell.counts.ok} valid / ${cell.expected} planned · ${cell.counts.refusal} refusals · ${cell.counts.invalid} invalid · ${cell.counts.error} pending errors. Counts cover the whole instrument; scale completeness is shown separately.`));
      host.append(node("p", `Run SHA-256: ${cell.run_id}`, "coverage"));
    }
    host.append(profileLink(row));
    host.hidden = false;
  }
  function heatmap(selected) {
    const result = node("table", undefined, "heatmap-table");
    result.append(node("caption", "Means in original units; colors show theoretical range position. Complete/planned repetitions appear below each mean."));
    const head = node("thead"), tr = node("tr");
    const first = node("th", "Model / scale"); first.scope = "col"; tr.append(first);
    cohort().columns.forEach(scale => {
      const th = node("th"); th.scope = "col";
      const button = node("button", scale.trait, "scale-heading");
      button.type = "button";
      button.title = `${scale.label} · ${scale.min}–${scale.max}. Select to inspect repetitions.`;
      button.addEventListener("click", () => {
        byId("dot-scale").value = scale.id; dotplot(rows()); byId("dot-section").scrollIntoView({ block: "start" });
      });
      th.append(button, node("small", scale.experiment));
      if (scale.label.endsWith("]")) th.append(node("small", scale.id.slice(0, 8)));
      tr.append(th);
    });
    head.append(tr); result.append(head);
    const body = node("tbody");
    selected.forEach(row => {
      const line = node("tr"), name = node("th"); name.scope = "row";
      name.append(profileLink(row), node("small", row.mode), node("small", row.digest.slice(0, 8)));
      line.append(name);
      cohort().columns.forEach(scale => {
        const cell = row.cells[scale.id], td = node("td");
        const button = node("button", undefined, "heatmap-cell"); button.type = "button";
        if (hasScore(cell)) {
          const p = Math.max(0, Math.min(100, cell.percent));
          button.style.backgroundColor = `hsl(155, 36%, ${97 - p * 0.67}%)`;
          button.style.color = p > 65 ? "#fff" : "#18332e";
          button.append(node("strong", format(cell.mean)), node("small", `${cell.n}/${cell.planned}`));
        } else {
          button.classList.add("missing-score");
          button.append(node("strong", "—"), node("small", cell ? `${cell.n}/${cell.planned}` : "No run"));
        }
        const description = `${row.model}, ${scale.label}: ${cellLabel(cell)}${hasScore(cell) ? `; ${format(cell.percent)}% of theoretical range; SD ${format(cell.sd)}` : ""}`;
        button.title = description; button.setAttribute("aria-label", description);
        button.addEventListener("click", () => inspect(row, scale, cell));
        td.append(button); line.append(td);
      });
      body.append(line);
    });
    result.append(body);
    byId("heatmap").replaceChildren(selected.length ? result : node("p", "No model variants match these filters."));
  }
  function chart(width, height, label) {
    const svg = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, width, height, role: "img", "aria-label": label, class: "comparison-chart" });
    svg.append(svgNode("title", {}, label));
    return svg;
  }
  function ticks(svg, min, max, start, end, cross, vertical) {
    for (let index = 0; index <= 4; index++) {
      const fraction = index / 4, point = start + (end - start) * fraction;
      svg.append(svgNode("text", vertical ? { x: cross - 10, y: point + 4, "text-anchor": "end" } : { x: point, y: cross + 24, "text-anchor": "middle" }, format(min + (max - min) * fraction)));
    }
  }
  function dotplot(selected) {
    const scale = column(byId("dot-scale").value);
    const width = 960, left = 300, right = 900, top = 48, bottom = top + selected.length * 56;
    const svg = chart(width, bottom + 65, `${scale.label}: complete repetition scores and means. The following expandable table provides all values.`);
    const x = value => left + (right - left) * position(value, scale.min, scale.max) / 100;
    ticks(svg, scale.min, scale.max, left, right, bottom, false);
    for (let index = 0; index <= 4; index++) {
      const point = left + (right - left) * index / 4;
      svg.append(svgNode("line", { x1: point, y1: top - 20, x2: point, y2: bottom, stroke: "#d7ded3" }));
    }
    selected.forEach((row, index) => {
      const y = top + index * 56, cell = row.cells[scale.id];
      svg.append(svgNode("text", { x: 8, y }, row.model));
      svg.append(svgNode("text", { x: 8, y: y + 17, class: "chart-note" }, `${row.digest.slice(0, 8)} · ${coverage(cell)}`));
      if (!hasScore(cell)) {
        svg.append(svgNode("text", { x: left, y }, cell ? "No complete repetition" : "No recorded run")); return;
      }
      cell.repetitions.forEach((rep, ri) => {
        const offset = cell.repetitions.length > 1 ? -7 + 14 * ri / (cell.repetitions.length - 1) : 0;
        const mark = svgNode("circle", { cx: x(rep.score), cy: y + offset, r: 4, fill: "white", stroke: color(row), "stroke-width": 2 });
        mark.append(svgNode("title", {}, `${row.model}: repetition ${rep.repetition}, ${format(rep.score)}`)); svg.append(mark);
      });
      const mean = svgNode("circle", { cx: x(cell.mean), cy: y, r: 6, fill: color(row), stroke: "white", "stroke-width": 1 });
      mean.append(svgNode("title", {}, `${row.model}: mean ${format(cell.mean)}, SD ${format(cell.sd)}, ${coverage(cell)}`)); svg.append(mean);
    });
    byId("dot-chart").replaceChildren(selected.length ? svg : node("p", "No model variants match these filters."));
    byId("dot-meta").textContent = `${scale.label} · ${scale.aggregation} · original range ${scale.min}–${scale.max} · ${selected.filter(row => hasScore(row.cells[scale.id])).length}/${selected.length} variants have a score. ${JSON.stringify(scale.protocol)} · questionnaire ${scale.questionnaire_hash.slice(0, 12)}`;
    byId("dot-table").replaceChildren(table(["Model variant", "Mean", "SD", "Complete / planned", "Repetition scores"], selected.map(row => {
      const cell = row.cells[scale.id];
      return [rowLabel(row), hasScore(cell) ? format(cell.mean) : "No score", format(cell && cell.sd), coverage(cell), cell ? cell.repetitions.map(rep => `#${rep.repetition}: ${format(rep.score)}`).join("; ") || "None" : "None"];
    })));
  }
  function scatter(selected) {
    const sx = column(byId("scatter-x").value), sy = column(byId("scatter-y").value);
    const eligible = pairs(selected, sx.id, sy.id);
    byId("scatter-status").textContent = `${eligible.length} plotted / ${selected.length} selected variants. ${selected.length - eligible.length} omitted because one or both scores are missing. X: ${sx.min}–${sx.max}; Y: ${sy.min}–${sy.max}.`;
    const width = 960, height = 620, left = 95, right = 735, top = 40, bottom = 510;
    const svg = chart(width, height, `${sx.label} against ${sy.label}. Points are unjittered means; labels may overlap. The following table provides all plotted values.`);
    const x = value => left + (right - left) * position(value, sx.min, sx.max) / 100;
    const y = value => bottom - (bottom - top) * position(value, sy.min, sy.max) / 100;
    for (let index = 0; index <= 4; index++) {
      const px = left + (right - left) * index / 4, py = bottom - (bottom - top) * index / 4;
      svg.append(svgNode("line", { x1: px, y1: top, x2: px, y2: bottom, stroke: "#d7ded3" }), svgNode("line", { x1: left, y1: py, x2: right, y2: py, stroke: "#d7ded3" }));
    }
    ticks(svg, sx.min, sx.max, left, right, bottom, false);
    ticks(svg, sy.min, sy.max, bottom, top, left, true);
    svg.append(svgNode("text", { x: (left + right) / 2, y: bottom + 60, "text-anchor": "middle" }, `X: ${sx.trait} (${sx.aggregation})`));
    svg.append(svgNode("text", { x: 20, y: (top + bottom) / 2, transform: `rotate(-90 20 ${(top + bottom) / 2})`, "text-anchor": "middle" }, `Y: ${sy.trait} (${sy.aggregation})`));
    eligible.forEach(row => {
      const cx = row.cells[sx.id], cy = row.cells[sy.id];
      const point = svgNode("circle", { cx: x(cx.mean), cy: y(cy.mean), r: 6, fill: color(row), stroke: "white", "stroke-width": 1 });
      point.append(svgNode("title", {}, `${rowLabel(row)}: X ${format(cx.mean)} (${coverage(cx)}), Y ${format(cy.mean)} (${coverage(cy)})`)); svg.append(point);
      svg.append(svgNode("text", { x: x(cx.mean) + 9, y: y(cy.mean) - 8, class: "scatter-label" }, row.model));
    });
    byId("scatter-chart").replaceChildren(eligible.length ? svg : node("p", "No selected model variant has scores on both axes."));
    byId("scatter-legend").replaceChildren();
    [...new Set(eligible.map(row => row.family))].sort().forEach(family => {
      const entry = node("span", family, "legend-entry"), swatch = node("span", "", "legend-swatch");
      swatch.style.backgroundColor = palette[families.indexOf(family) % palette.length];
      entry.prepend(swatch); byId("scatter-legend").append(entry);
    });
    byId("scatter-table").replaceChildren(table(["Model variant", sx.label, "X complete / planned", sy.label, "Y complete / planned"], eligible.map(row => [rowLabel(row), format(row.cells[sx.id].mean), coverage(row.cells[sx.id]), format(row.cells[sy.id].mean), coverage(row.cells[sy.id])])));
  }
  function render() {
    const selected = rows();
    byId("comparison-status").textContent = `${selected.length} of ${cohort().rows.length} model variants shown · ${cohort().columns.length} score series. Missing scores are not imputed.`;
    byId("cell-detail").hidden = true;
    heatmap(selected); dotplot(selected); scatter(selected);
  }
  function changeGroup() {
    const group = cohort();
    options(byId("family-select"), [["", "All recorded families"], ...[...new Set(group.rows.map(row => row.family))].sort().map(family => [family, family])]);
    options(byId("model-select"), group.rows.map(row => [row.id, rowLabel(row)]));
    const entries = group.columns.map(scale => [scale.id, scale.label]);
    ["dot-scale", "scatter-x", "scatter-y"].forEach(id => options(byId(id), entries, byId(id).value));
    if (byId("scatter-y").value === byId("scatter-x").value && entries.length > 1) byId("scatter-y").value = entries[1][0];
    byId("cohort-details").textContent = JSON.stringify({ id: group.id, backend: group.backend, hardware: group.hardware }, null, 2);
    render();
  }
  options(byId("cohort-select"), data.cohorts.map(group => [group.id, `Ollama ${group.backend.version} · ${group.rows.length} variants · group ${group.id.slice(0, 8)}`]));
  byId("cohort-select").addEventListener("change", changeGroup);
  ["family-select", "model-select"].forEach(id => byId(id).addEventListener("change", render));
  byId("comparison-search").addEventListener("input", render);
  byId("clear-models").addEventListener("click", () => { [...byId("model-select").options].forEach(option => { option.selected = false; }); render(); });
  byId("dot-scale").addEventListener("change", () => dotplot(rows()));
  ["scatter-x", "scatter-y"].forEach(id => byId(id).addEventListener("change", () => scatter(rows())));
  changeGroup();
  app.hidden = false;
  byId("comparison-static").hidden = true;
})();
