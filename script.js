(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);

  const FRIEND_TONE = [
    { min: 80, msg: '오늘 진짜 산책각이야. 친구 불러봐 🚶' },
    { min: 60, msg: '괜찮은 정도. 잠깐 바람 쐬기엔 OK' },
    { min: 40, msg: '굳이? 안 나가도 되는 날인 듯' },
    { min: 0,  msg: '오늘은 매점 ㄱㄱ. 산책은 패스하자' },
  ];
  const friendMessage = (s) => FRIEND_TONE.find((t) => s >= t.min).msg;

  const scoreClass = (s) => {
    if (s >= 80) return 'good';
    if (s >= 60) return 'normal';
    if (s >= 40) return 'bad';
    return 'worst';
  };
  const airClass = (label) => ({
    '좋음': 'good', '보통': 'normal',
    '나쁨': 'bad', '매우나쁨': 'worst',
    '측정값 없음': 'normal',
  }[label] || 'normal');

  const fmtHour = (h) => `${h}시`;
  const fmtTemp = (t) => `${Math.round(t)}°`;

  // 기본 추천 코스 색상 팔레트 (자동 할당)
  const COLOR_PALETTE = ['#1ec979', '#3182f6', '#ff8c42', '#ff5c5c', '#9b59ff', '#00bcd4'];

  let state = {
    score: 0,
    routes: [],
    schedule: [],
    hourly: [],
    school: { lat: 36.119, lon: 126.974, name: '학교' },
  };

  // ──────────────────────────────────────────────────────────
  // 데이터 로딩
  // ──────────────────────────────────────────────────────────
  async function load() {
    const loader = $('loader');
    const errBox = $('error');
    try {
      const [data, routes] = await Promise.all([
        fetch(`data.json?t=${Date.now()}`).then((r) => {
          if (!r.ok) throw new Error(`data.json HTTP ${r.status}`);
          return r.json();
        }),
        fetch(`routes.json?t=${Date.now()}`).then((r) => {
          if (!r.ok) throw new Error(`routes.json HTTP ${r.status}`);
          return r.json();
        }),
      ]);
      state.score = data.best_time?.score || 0;
      state.routes = (routes.routes || []).filter((r) => r && !r._placeholder);
      state.schedule = routes.schedule || [];
      state.hourly = data.hourly || [];
      state.school = routes.school || state.school;

      renderScoreCards(data);
      renderSchedule();
      renderHourly(data);
      initMap();
      renderFooter(data);
      loader.classList.add('hidden');
    } catch (e) {
      console.error(e);
      loader.classList.add('hidden');
      errBox.hidden = false;
      $('errorText').textContent =
        '데이터를 불러오지 못했어. py fetch_data.py 실행 + routes.json 존재 여부 확인.';
    }
  }

  // ──────────────────────────────────────────────────────────
  // 카드/그리드 렌더
  // ──────────────────────────────────────────────────────────
  function renderScoreCards(data) {
    $('chipSchool').textContent = data.school || '학교';
    $('heroSub').textContent =
      data.best_time
        ? friendMessage(data.best_time.score)
        : '오늘은 데이터가 부족해…';

    if (data.best_time) {
      const bt = data.best_time;
      $('bestCard').hidden = false;
      $('bestTime').textContent = fmtHour(bt.hour);
      $('bestScore').textContent = `점수 ${bt.score}`;
      $('bestDetail').textContent =
        `${bt.sky_text} · ${fmtTemp(bt.tmp)} · 강수확률 ${Math.round(bt.pop)}% · 풍속 ${bt.wsd}m/s`;
    }

    const air = data.air;
    $('airCard').hidden = false;
    $('airPm10').textContent = air.pm10 < 0 ? '—' : `${air.pm10} ㎍/㎥`;
    $('airPm25').textContent = air.pm25 < 0 ? '—' : `${air.pm25} ㎍/㎥`;
    const badge = $('airBadge');
    badge.textContent = air.label;
    badge.className = `air-card__badge ${airClass(air.label)}`;
    $('airMeta').textContent =
      `${air.station || '측정소 정보 없음'} · ${air.measured_at || ''}`;
  }

  function renderHourly(data) {
    const grid = $('hourlyGrid');
    grid.innerHTML = '';
    data.hourly.forEach((h) => {
      const cell = document.createElement('div');
      cell.className = `hcell ${scoreClass(h.score)}`;
      cell.dataset.hour = h.hour;
      cell.innerHTML = `
        <div class="hcell__hour">${fmtHour(h.hour)}</div>
        <div class="hcell__score">${Math.round(h.score)}</div>
        <div class="hcell__tmp">${fmtTemp(h.tmp)} · ${h.sky_text}</div>
      `;
      cell.title = h.note;
      grid.appendChild(cell);
    });
    $('hourlySection').hidden = false;
    $('howtoSection').hidden = false;
  }

  function renderFooter(data) {
    $('updatedAt').textContent =
      `업데이트 · ${data.generated_at?.replace('T', ' ') || '-'}`;
  }

  // ──────────────────────────────────────────────────────────
  // 학교 일과 슬롯별 점수 계산 + 렌더
  // ──────────────────────────────────────────────────────────
  function parseHHMM(s) {
    const [h, m] = (s || '00:00').split(':').map((v) => parseInt(v, 10));
    return h + (m || 0) / 60;
  }

  function findSlotMatches(slot) {
    const startH = parseHHMM(slot.start);
    const endH = parseHHMM(slot.end);
    const now = new Date();

    // hourly 데이터 중 1) 미래 시점 2) 시간이 슬롯 범위에 걸치는 것
    const matches = state.hourly.filter((h) => {
      const dt = new Date(h.datetime);
      if (dt < now) return false; // 이미 지난 시간은 제외
      // h.hour 가 [floor(startH), ceil(endH)) 안에 있으면 매칭
      const fHour = Math.floor(startH);
      const cHour = Math.ceil(endH);
      return h.hour >= fHour && h.hour < cHour;
    });

    if (matches.length === 0) return null;

    const sum = matches.reduce((a, b) => a + b.score, 0);
    const avg = Math.round((sum / matches.length) * 10) / 10;
    const best = matches.reduce((a, b) => (b.score > a.score ? b : a));
    return { matches, avg, best };
  }

  function renderSchedule() {
    if (!state.schedule || state.schedule.length === 0) return;
    const list = $('scheduleList');
    list.innerHTML = '';

    // 모든 슬롯 점수 계산 → best 슬롯 찾기 (badge용)
    const computed = state.schedule.map((slot) => ({
      slot,
      result: findSlotMatches(slot),
    }));
    const valid = computed.filter((c) => c.result);
    const bestSlotId = valid.length
      ? valid.reduce((a, b) => (b.result.avg > a.result.avg ? b : a)).slot.id
      : null;

    computed.forEach(({ slot, result }) => {
      const li = document.createElement('li');
      let cls = 's-na';
      let scoreText = '—';
      let subText = `${slot.start}~${slot.end} · ${slot.subtitle}`;

      if (result) {
        const avg = result.avg;
        cls = avg >= 80 ? 's-good' : avg >= 60 ? 's-normal' : avg >= 40 ? 's-bad' : 's-worst';
        scoreText = Math.round(avg);
        const best = result.best;
        subText = `${slot.start}~${slot.end} · ` +
          `베스트 ${best.hour}시 · ${best.sky_text} ${Math.round(best.tmp)}°`;
      } else {
        subText = `${slot.start}~${slot.end} · 오늘은 데이터 없음 (지난 시간 또는 예보 범위 밖)`;
      }

      li.className = `schedule-row ${cls}`;
      const isBest = slot.id === bestSlotId;
      li.innerHTML = `
        <div class="schedule-row__icon">${slot.icon || '🕒'}</div>
        <div class="schedule-row__main">
          <div class="schedule-row__label">
            ${slot.label}
            <span class="time-tag">${slot.start}~${slot.end}</span>
            ${isBest && result ? '<span class="badge-best">오늘 추천</span>' : ''}
          </div>
          <div class="schedule-row__sub">${subText}</div>
        </div>
        <div class="schedule-row__score">${scoreText}</div>
      `;
      li.addEventListener('click', () => {
        if (!result) return;
        // 시간대별 그리드 해당 시간으로 스크롤만 (지도는 고정 유지)
        const target = document.querySelector(`[data-hour="${result.best.hour}"]`);
        if (target) {
          target.scrollIntoView({ behavior: 'smooth', block: 'center' });
          target.classList.add('hcell--flash');
          setTimeout(() => target.classList.remove('hcell--flash'), 1200);
        }
      });
      list.appendChild(li);
    });

    $('scheduleCard').hidden = false;
  }

  // ──────────────────────────────────────────────────────────
  // 지도 초기화 (위성 사진 + OSM 토글)
  // ──────────────────────────────────────────────────────────
  let map;
  let routeLayers = {};
  let userRouteLayers = {};
  let drawing = false;
  let drawPoints = [];
  let drawPolyline = null;

  function initMap() {
    const { lat, lon } = state.school;

    map = L.map('map', {
      zoomControl: false,
      attributionControl: true,
      dragging: false,
      touchZoom: false,
      doubleClickZoom: false,
      scrollWheelZoom: false,
      boxZoom: false,
      keyboard: false,
    }).setView([lat, lon], 18);

    const satellite = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      {
        maxZoom: 19,
        attribution:
          'Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, GIS User Community',
      }
    );
    const osm = L.tileLayer(
      'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors',
      }
    );
    satellite.addTo(map);
    L.control
      .layers({ '위성 사진': satellite, '일반 지도': osm }, null, { position: 'topright' })
      .addTo(map);

    // 학교 마커
    const schoolIcon = L.divIcon({
      className: 'school-marker',
      html: '학',
      iconSize: [32, 32],
      iconAnchor: [16, 16],
    });
    L.marker([lat, lon], { icon: schoolIcon })
      .addTo(map)
      .bindPopup(`<b>${state.school.name}</b><br/>산책 출발점`);

    renderRoutes();
    renderUserRoutes();
    setupDrawHandlers();

    // 등록된 코스 + 학교 마커가 모두 보이도록 자동 줌 (디폴트 view 고정)
    fitMapToRoutes();
  }

  function fitMapToRoutes() {
    const points = state.routes.flatMap((r) => r.path || []);
    points.push([state.school.lat, state.school.lon]);
    if (points.length < 2) return;
    map.fitBounds(points, {
      padding: [30, 30],
      maxZoom: 19,
      animate: false,
    });
  }

  // 지도 인터랙션 토글 (평소 OFF, 그리기 모드만 ON)
  const INTERACTIONS = [
    'dragging', 'touchZoom', 'doubleClickZoom',
    'scrollWheelZoom', 'boxZoom', 'keyboard',
  ];
  let _zoomCtrl = null;
  function setMapInteractive(on) {
    INTERACTIONS.forEach((name) => {
      const handler = map[name];
      if (!handler) return;
      if (on) handler.enable();
      else handler.disable();
    });
    if (on && !_zoomCtrl) {
      _zoomCtrl = L.control.zoom({ position: 'topleft' }).addTo(map);
    } else if (!on && _zoomCtrl) {
      map.removeControl(_zoomCtrl);
      _zoomCtrl = null;
    }
  }

  function renderRoutes() {
    Object.values(routeLayers).forEach((l) => map.removeLayer(l));
    routeLayers = {};
    const list = $('routeList');
    list.innerHTML = '';

    if (state.routes.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'route-list__empty';
      empty.innerHTML =
        '아직 등록된 추천 코스가 없어요.<br/>' +
        '아래 <b>코스 그리기</b>에서 위성 사진을 보고 점을 찍어 만들어 보세요.';
      list.appendChild(empty);
      return;
    }

    state.routes.forEach((r, idx) => {
      const color = r.color || COLOR_PALETTE[idx % COLOR_PALETTE.length];
      const recommended = state.score >= (r.min_score || 0);
      const opacity = recommended ? 0.9 : 0.4;
      const weight = recommended ? 5 : 3;

      const polyline = L.polyline(r.path, {
        color,
        weight,
        opacity,
        lineJoin: 'round',
      }).addTo(map);
      polyline.bindPopup(
        `<b>${r.name}</b><br/>${r.subtitle || ''}<br/>` +
        `약 ${r.duration_min || '?'}분 · ${r.distance_km || '?'}km`
      );
      routeLayers[r.id || `r${idx}`] = polyline;

      const card = document.createElement('div');
      card.className = `route-card ${recommended ? 'recommended' : ''}`;
      card.style.color = color;
      card.innerHTML = `
        <div class="route-card__dot"></div>
        <div class="route-card__main">
          <div class="route-card__title">
            <span style="color: var(--text)">${r.name}</span>
            ${recommended ? '<span class="badge-rec">추천</span>' : ''}
          </div>
          <div class="route-card__sub">${r.subtitle || ''}</div>
        </div>
        <div class="route-card__meta">${r.duration_min || '?'}분 · ${r.distance_km || '?'}km</div>
      `;
      card.addEventListener('click', () => polyline.openPopup());
      card.addEventListener('mouseenter', () => polyline.setStyle({ weight: weight + 2 }));
      card.addEventListener('mouseleave', () => polyline.setStyle({ weight }));
      list.appendChild(card);
    });
  }

  // ──────────────────────────────────────────────────────────
  // 그리기 모드
  // ──────────────────────────────────────────────────────────
  function setupDrawHandlers() {
    $('drawStart').addEventListener('click', startDrawing);
    $('drawCancel').addEventListener('click', cancelDrawing);
    $('drawSave').addEventListener('click', saveDrawing);
    $('drawUndo').addEventListener('click', undoPoint);
    $('jsonCopy').addEventListener('click', copyJson);
  }

  function startDrawing() {
    drawing = true;
    drawPoints = [];
    if (drawPolyline) map.removeLayer(drawPolyline);
    drawPolyline = L.polyline([], {
      color: '#ff5c5c',
      weight: 5,
      opacity: 0.95,
      dashArray: '6, 8',
    }).addTo(map);

    // 그리기 중에는 지도 자유 이동/줌 허용
    setMapInteractive(true);
    map.getContainer().classList.add('drawing');
    map.on('click', onMapClick);

    $('drawStart').hidden = true;
    $('drawActions').hidden = false;
    $('jsonOutputWrap').hidden = true;
    $('drawHint').textContent = '위성 사진에서 점을 클릭해서 경로를 만들어. 다 찍으면 저장 눌러.';
  }

  function onMapClick(e) {
    if (!drawing) return;
    drawPoints.push([
      Math.round(e.latlng.lat * 1e5) / 1e5,
      Math.round(e.latlng.lng * 1e5) / 1e5,
    ]);
    drawPolyline.setLatLngs(drawPoints);
  }

  function undoPoint() {
    if (drawPoints.length === 0) return;
    drawPoints.pop();
    drawPolyline.setLatLngs(drawPoints);
  }

  function cancelDrawing() {
    drawing = false;
    map.off('click', onMapClick);
    map.getContainer().classList.remove('drawing');
    if (drawPolyline) {
      map.removeLayer(drawPolyline);
      drawPolyline = null;
    }
    drawPoints = [];
    $('drawStart').hidden = false;
    $('drawActions').hidden = true;
    $('drawName').value = '';
    $('drawMinutes').value = '';
    $('drawSubtitle').value = '';
    $('drawHint').textContent = '위성 사진에서 점을 찍어 산책 경로를 직접 만들어봐';

    // 그리기 종료 → 지도 다시 고정 + 디폴트 view 복귀
    setMapInteractive(false);
    fitMapToRoutes();
  }

  function saveDrawing() {
    if (drawPoints.length < 2) {
      alert('최소 2개의 점을 찍어야 코스가 돼요.');
      return;
    }
    const category = document.querySelector('input[name="drawCategory"]:checked').value;
    const name = ($('drawName').value || '').trim() || '새 코스';
    const subtitle = ($('drawSubtitle').value || '').trim() || '';
    const minutes = parseInt($('drawMinutes').value, 10) || estimateMinutes(drawPoints);
    const minScore = parseInt($('drawMinScore').value, 10) || 60;
    const distance = estimateKm(drawPoints);

    if (category === 'default') {
      const colorIdx = state.routes.length % COLOR_PALETTE.length;
      const route = {
        id: slugify(name) || `route_${Date.now()}`,
        name,
        subtitle,
        duration_min: minutes,
        distance_km: distance,
        color: COLOR_PALETTE[colorIdx],
        min_score: minScore,
        path: drawPoints.slice(),
      };
      // 화면에서 즉시 미리보기 (state 추가 + 다시 렌더)
      state.routes.push(route);
      renderRoutes();
      // localStorage 백업 (실수로 클립보드를 덮어써도 복구 가능)
      backupDefaultRoute(route);
      // JSON 출력
      showJsonOutput(route);
    } else {
      const list = getUserRoutes();
      list.push({
        id: 'u_' + Date.now(),
        name,
        path: drawPoints.slice(),
        created_at: new Date().toISOString(),
        distance_km: distance,
      });
      saveUserRoutes(list);
      renderUserRoutes();
    }

    cancelDrawing();
  }

  function showJsonOutput(route) {
    const wrap = $('jsonOutputWrap');
    const pre = $('jsonOutput');
    pre.textContent = JSON.stringify(route, null, 2);
    wrap.hidden = false;
    wrap.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  async function copyJson() {
    const text = $('jsonOutput').textContent;
    try {
      await navigator.clipboard.writeText(text);
      const btn = $('jsonCopy');
      const orig = btn.textContent;
      btn.textContent = '복사 완료!';
      setTimeout(() => (btn.textContent = orig), 1500);
    } catch {
      alert('클립보드 복사 실패. 수동으로 선택해서 복사해 주세요.');
    }
  }

  function slugify(name) {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9가-힣]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 30);
  }

  function estimateKm(points) {
    if (points.length < 2) return 0;
    let km = 0;
    for (let i = 1; i < points.length; i++) {
      km += haversine(points[i - 1], points[i]);
    }
    return Math.round(km * 100) / 100;
  }

  function estimateMinutes(points) {
    // 도보 평균 속도 5km/h 가정
    const km = estimateKm(points);
    return Math.max(1, Math.round((km / 5) * 60));
  }

  function haversine(a, b) {
    const R = 6371;
    const toRad = (d) => (d * Math.PI) / 180;
    const dLat = toRad(b[0] - a[0]);
    const dLon = toRad(b[1] - a[1]);
    const lat1 = toRad(a[0]);
    const lat2 = toRad(b[0]);
    const x =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(x));
  }

  // ──────────────────────────────────────────────────────────
  // 기본 추천 코스 백업 (실수로 클립보드 덮어써도 복구 가능)
  // ──────────────────────────────────────────────────────────
  const BACKUP_KEY = 'walkFinder.defaultRouteBackup.v1';
  function backupDefaultRoute(route) {
    try {
      const list = JSON.parse(localStorage.getItem(BACKUP_KEY) || '[]');
      list.push({ savedAt: new Date().toISOString(), route });
      localStorage.setItem(BACKUP_KEY, JSON.stringify(list));
    } catch (e) {
      console.warn('백업 실패', e);
    }
  }
  // 콘솔에서 window.recoverDefaultRoutes() 호출하면 백업된 코스를 모두 출력
  window.recoverDefaultRoutes = function () {
    try {
      return JSON.parse(localStorage.getItem(BACKUP_KEY) || '[]');
    } catch { return []; }
  };

  // ──────────────────────────────────────────────────────────
  // localStorage 사용자 코스
  // ──────────────────────────────────────────────────────────
  const STORE_KEY = 'walkFinder.userRoutes.v1';

  function getUserRoutes() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY) || '[]'); }
    catch { return []; }
  }
  function saveUserRoutes(list) {
    localStorage.setItem(STORE_KEY, JSON.stringify(list));
  }
  function deleteUserRoute(id) {
    const list = getUserRoutes().filter((r) => r.id !== id);
    saveUserRoutes(list);
    renderUserRoutes();
  }

  function renderUserRoutes() {
    Object.values(userRouteLayers).forEach((l) => map.removeLayer(l));
    userRouteLayers = {};

    const container = $('userRoutes');
    container.innerHTML = '';
    const list = getUserRoutes();
    if (list.length === 0) return;

    const heading = document.createElement('div');
    heading.className = 'route-card__sub';
    heading.style.padding = '4px 0 4px';
    heading.style.fontWeight = '700';
    heading.style.color = 'var(--text)';
    heading.textContent = `내가 그린 코스 (${list.length})`;
    container.appendChild(heading);

    list.forEach((r) => {
      const polyline = L.polyline(r.path, {
        color: '#ffd000',
        weight: 4,
        opacity: 0.9,
        dashArray: '4, 6',
      }).addTo(map);
      polyline.bindPopup(`<b>${r.name}</b><br/>약 ${r.distance_km}km`);
      userRouteLayers[r.id] = polyline;

      const card = document.createElement('div');
      card.className = 'route-card';
      card.style.color = '#caa400';
      card.innerHTML = `
        <div class="route-card__dot"></div>
        <div class="route-card__main">
          <div class="route-card__title">${r.name}</div>
          <div class="route-card__sub">약 ${r.distance_km}km · ${r.path.length}개 점</div>
        </div>
        <button class="btn btn-ghost" data-id="${r.id}">삭제</button>
      `;
      card.addEventListener('click', (e) => {
        if (e.target.tagName === 'BUTTON') return;
        polyline.openPopup();
      });
      card.querySelector('button').addEventListener('click', (e) => {
        e.stopPropagation();
        if (confirm(`'${r.name}' 코스를 삭제할까?`)) deleteUserRoute(r.id);
      });
      container.appendChild(card);
    });
  }

  load();
})();
