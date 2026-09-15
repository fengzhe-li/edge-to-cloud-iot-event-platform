/* Read-only operational analytics. No credentials or authentication bypass. */
(() => {
  const byId = id => document.getElementById(id);
  const time = value => {
    if (value == null) return 'Unavailable';
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? 'Unavailable' : date.toISOString().replace('T', ' ');
  };
  function table(id, headings, rows) {
    const target = byId(id);
    target.replaceChildren();
    if (!rows.length) { target.textContent = 'No records available.'; return; }
    const node = document.createElement('table');
    node.className = 'audit-table';
    const header = node.createTHead().insertRow();
    headings.forEach(label => { const th = document.createElement('th'); th.textContent = label; header.append(th); });
    const body = node.createTBody();
    rows.forEach(values => { const row = body.insertRow(); values.forEach(value => { row.insertCell().textContent = value ?? 'Unavailable'; }); });
    target.append(node);
  }
  function render(data) {
    const incidents = data.incidents;
    byId('analytics-count').textContent = String(incidents.incident_count);
    byId('analytics-frequency').textContent = `${incidents.events_per_hour.toFixed(3)} observed transitions/hour`;
    byId('analytics-online').textContent = `${data.online_device_count} / ${data.device_count} online now`;
    byId('analytics-availability').textContent = 'Historical availability unavailable — latest heartbeat only.';
    byId('analytics-response').textContent = data.response_times.supported
      ? `${data.response_times.mean_seconds} seconds` : 'Unavailable — RFID scans have no incident acknowledgement key.';
    byId('analytics-first-wet').textContent = `${incidents.first_observed_wet_count} first-observed wet records excluded from incident count; ${incidents.ambiguous_reading_count} readings with conflicting timestamps.`;
    byId('analytics-stamp').textContent = `Generated ${time(data.generated_at)}. History: ${time(data.window.start)} to ${time(data.window.end)} (end excluded). Device health and settings are current.`;
    table('analytics-devices', ['Device','Health','Last heartbeat (UTC)','Reported uptime'], data.devices.map(d => [
      d.device_id, d.quiet_but_online ? 'Quiet but online' : d.status,
      d.last_seen_ts == null ? 'Unavailable' : time(Number(d.last_seen_ts)),
      d.reported_uptime_seconds == null ? 'Unavailable' : `${d.reported_uptime_seconds} s at last heartbeat`
    ]));
    table('analytics-zones', ['Current zone mapping','Observed incidents'], Object.entries(incidents.by_zone).map(([z,count]) => [z === 'unmapped' ? 'Unmapped' : `Zone ${z}`,count]));
    table('analytics-incidents', ['Time (UTC)','Device / sensor','Classification'], incidents.recent_incidents.map(r => [time(r.timestamp_ms),`${r.device_id} / ${r.sensor_id}`,r.classification === 'observed_wet_transition' ? 'Observed wet transition' : 'First observed wet; onset unknown']));
    table('analytics-history', ['Time (UTC)','Device / sensor','State transition'], incidents.state_transitions.map(r => [time(r.timestamp_ms),`${r.device_id} / ${r.sensor_id}`,`${r.from_state ?? 'Not observed'} → ${r.to_state}${r.ambiguous_timestamp ? ' (ambiguous timestamp)' : ''}`]));
    table('analytics-current-state', ['Sensor','Current state','Updated (UTC)'], data.current_sensor_state.map(r => [r.sensor_id,r.state,time(Number(r.updated_ts))]));
    table('analytics-settings', ['Device / sensor','Active'], data.configuration.map(r => [`${r.device_id} / ${r.sensor_id}`,r.active ? 'Yes' : 'No']));
    table('analytics-thresholds', ['Device / sensor','Current threshold'], data.thresholds.map(r => [`${r.device_name} / ${r.sensor_id}`,r.threshold_value]));
    byId('analytics-results').hidden = false;
    byId('analytics-status').textContent = `Summary loaded. Showing up to 20 incidents and 50 transitions; counts cover the complete requested window. ${data.response_times.rfid_scans_in_window} RFID scans, not correlated to incidents.`;
  }
  async function refresh() {
    const base = window.APP_CONFIG?.ANALYTICS_API_BASE;
    if (!base || base.includes('YOUR_')) {
      byId('analytics-status').textContent = 'Configure an authorized analytics endpoint to load operational data. No sample metrics are shown.';
      return;
    }
    const button = byId('analytics-refresh');
    button.disabled = true;
    byId('analytics-results').hidden = true;
    byId('analytics-status').textContent = 'Loading operational data…';
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const url = new URL(base, window.location.href);
      url.searchParams.set('window_hours', byId('analytics-window').value);
      // A deployment may provide an authorized transport. No signing keys belong here.
      const transport = window.analyticsFetch || window.fetch.bind(window);
      const result = await transport(url.toString(), {method:'GET',cache:'no-store',signal:controller.signal});
      const data = await result.json();
      if (!result.ok || !data.ok) throw new Error(data.error || `HTTP ${result.status}`);
      render(data);
    } catch (error) {
      byId('analytics-status').textContent = `Analytics unavailable: ${error.message}. Existing live controls are unchanged.`;
    } finally { clearTimeout(timer); button.disabled = false; }
  }
  byId('analytics-refresh').addEventListener('click', refresh);
})();
