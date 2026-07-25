// ===== Supermarket SVG Floor Plan =====
// Zones are drawn INSIDE the map; sensors are mounted ON specific shelves.

(function () {
    const NS = 'http://www.w3.org/2000/svg';
    const W = 920, H = 540;

    function el(tag, attrs, parent) {
        const e = document.createElementNS(NS, tag);
        for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
        if (parent) parent.appendChild(e);
        return e;
    }
    function txt(parent, content, attrs) {
        const t = el('text', attrs, parent);
        t.textContent = content;
        return t;
    }

    // Layout:
    //   Zone shelf area:  y 54 – 356  (gives room for zone header text at top)
    //   Main aisle:       y 356 – 396
    //   Checkout strip:   y 396 – 530
    const ZONE_DEFS = {
        1: { x: 8, y: 8, w: 290, h: 348, fill: 'rgba(108,99,255,0.08)', stroke: 'rgba(108,99,255,0.30)', wet: { fill: 'rgba(108,99,255,0.22)', stroke: 'rgba(108,99,255,0.75)' } },
        2: { x: 312, y: 8, w: 266, h: 348, fill: 'rgba(0,198,255,0.08)', stroke: 'rgba(0,198,255,0.30)', wet: { fill: 'rgba(0,198,255,0.22)', stroke: 'rgba(0,198,255,0.75)' } },
        3: { x: 592, y: 8, w: 320, h: 348, fill: 'rgba(0,214,143,0.08)', stroke: 'rgba(0,214,143,0.30)', wet: { fill: 'rgba(0,214,143,0.22)', stroke: 'rgba(0,214,143,0.75)' } },
    };
    const ZONE_NAMES = { 1: 'Beverages & Dairy', 2: 'Electronics & General', 3: 'Produce & Fresh' };
    const ZONE_COLORS = { 1: '#6C63FF', 2: '#00c6ff', 3: '#00d68f' };

    // Shelves start below the zone header band
    const SHELF_Y = 58, SHELF_H = 280, SHELF_W = 52, SHELF_LEVELS = 5;

    const Z1X = [16, 88, 160, 232];
    const Z2X = [320, 404, 488];
    const Z3X = [600, 692, 784];

    const SHELVES = [
        ...Z1X.map(x => ({ zone: 1, x, y: SHELF_Y, w: SHELF_W, h: SHELF_H })),
        ...Z2X.map(x => ({ zone: 2, x, y: SHELF_Y, w: SHELF_W, h: SHELF_H })),
        ...Z3X.map(x => ({ zone: 3, x, y: SHELF_Y, w: SHELF_W, h: SHELF_H })),
    ];

    const SENSOR_DEFS = [
        { id: 0, shelfIdx: 0, yOff: 50 },   // Zone 1, aisle 1
        { id: 1, shelfIdx: 2, yOff: 190 },  // Zone 1, aisle 3
        { id: 2, shelfIdx: 5, yOff: 80 },   // Zone 2, aisle 2
        { id: 3, shelfIdx: 7, yOff: 190 },  // Zone 3, aisle 2
        { id: 4, shelfIdx: 9, yOff: 80 },   // Zone 3, aisle 3
        { id: 5, shelfIdx: 4, yOff: 220 },  // Zone 2, aisle 1
    ];

    function buildDefs(svg) {
        const defs = el('defs', {}, svg);
        const f = el('filter', { id: 'sh', x: '-20%', y: '-20%', width: '150%', height: '150%' }, defs);
        el('feDropShadow', { dx: 2, dy: 3, stdDeviation: 3, 'flood-color': 'rgba(0,0,0,0.13)' }, f);
    }

    function drawZoneFloor(svg) {
        for (const [id, z] of Object.entries(ZONE_DEFS)) {
            // Colored zone floor
            el('rect', { id: `zone-floor-${id}`, x: z.x, y: z.y, width: z.w, height: z.h, fill: z.fill, rx: 7 }, svg);
            el('rect', {
                id: `zone-border-${id}`, x: z.x, y: z.y, width: z.w, height: z.h, fill: 'none',
                stroke: z.stroke, 'stroke-width': 1.5, rx: 7, 'stroke-dasharray': '6 3'
            }, svg);

            // Zone header band inside the zone
            const col = ZONE_COLORS[id];
            el('rect', {
                x: z.x + 1, y: z.y + 1, width: z.w - 2, height: 44, fill: col,
                opacity: 0.12, rx: '7 7 0 0'
            }, svg);

            // Zone number badge
            el('rect', { x: z.x + 10, y: z.y + 10, width: 24, height: 24, rx: 6, fill: col }, svg);
            txt(svg, String(id), {
                x: z.x + 22, y: z.y + 27,
                'text-anchor': 'middle', fill: '#fff',
                'font-size': 13, 'font-weight': 800, 'font-family': 'Inter,sans-serif'
            });

            // Zone name — full text, positioned to the right of the badge
            txt(svg, ZONE_NAMES[id], {
                x: z.x + 42, y: z.y + 23,
                fill: col, 'font-size': 10.5, 'font-weight': 700,
                'font-family': 'Inter,sans-serif', opacity: 0.95
            });
            txt(svg, `ZONE ${id}`, {
                x: z.x + 42, y: z.y + 36,
                fill: col, 'font-size': 8, 'font-weight': 600,
                'font-family': 'Inter,sans-serif', opacity: 0.7, 'letter-spacing': 1.5
            });
        }
    }

    function drawAisles(svg) {
        // Vertical aisle dividers
        el('rect', { x: 298, y: 8, width: 14, height: 348, fill: '#e2e2ea' }, svg);
        el('rect', { x: 578, y: 8, width: 14, height: 348, fill: '#e2e2ea' }, svg);

        // Main horizontal circulation aisle
        el('rect', { x: 8, y: 356, width: 904, height: 40, fill: '#e8e8f0' }, svg);
        // Aisle label
        txt(svg, 'MAIN AISLE', {
            x: 460, y: 380, 'text-anchor': 'middle',
            fill: '#aaaabc', 'font-size': 9, 'font-weight': 600,
            'font-family': 'Inter,sans-serif', 'letter-spacing': 3
        });
        // Direction arrows
        for (let ax = 60; ax < 880; ax += 100) {
            el('polygon', { points: `${ax},362 ${ax + 10},371 ${ax},380`, fill: 'rgba(160,160,180,0.35)' }, svg);
        }
    }

    function drawShelf(svg, s) {
        const g = el('g', {}, svg);
        const { x, y, w, h } = s;
        el('rect', { x, y, width: w, height: h, fill: '#f0f0f5', stroke: '#c4c4d2', 'stroke-width': 1, rx: 4, filter: 'url(#sh)' }, g);
        // Right depth face
        el('rect', { x: x + w, y: y + 5, width: 6, height: h, fill: '#bbbbc8' }, g);
        // Bottom depth face
        el('rect', { x: x + 4, y: y + h, width: w + 2, height: 5, fill: '#b0b0c0' }, g);
        // Shelf level lines
        for (let i = 1; i <= SHELF_LEVELS; i++) {
            const ly = y + (h / (SHELF_LEVELS + 1)) * i;
            el('line', { x1: x + 4, y1: ly, x2: x + w - 4, y2: ly, stroke: '#c0c0ce', 'stroke-width': 0.8 }, g);
        }
        // Top highlight
        el('line', { x1: x + 3, y1: y, x2: x + w - 3, y2: y, stroke: 'rgba(255,255,255,0.9)', 'stroke-width': 2 }, g);
        return g;
    }

    function drawSensor(svg, sensorId, sx, sy) {
        const g = el('g', { id: `snode-${sensorId}`, class: 'snode', cursor: 'pointer' }, svg);
        g.addEventListener('click', e => {
            e.stopPropagation();
            if (typeof openSensorPopover === 'function') openSensorPopover(e, sensorId);
        });
        // Bracket
        el('rect', { x: sx - 7, y: sy - 5, width: 14, height: 9, fill: '#22233a', rx: 2 }, g);
        // Pulse ring
        el('circle', { class: 'snode-ring', cx: sx, cy: sy, r: 11, fill: 'none', stroke: 'transparent', 'stroke-width': 2 }, g);
        // LED
        el('circle', { class: 'snode-led', cx: sx, cy: sy, r: 3.8, fill: '#00d68f' }, g);
        // ID label — below the sensor
        txt(g, `S${sensorId}`, {
            x: sx, y: sy + 17,
            'text-anchor': 'middle', 'font-size': 8.5,
            'font-weight': 700, 'font-family': 'Inter,sans-serif',
            fill: '#6a6a80', class: 'snode-label'
        });
        return g;
    }

    function drawCheckout(svg) {
        const CY = 396, CH = 134;
        // Checkout area background
        el('rect', { x: 8, y: CY, width: 904, height: CH, fill: 'rgba(255,170,0,0.06)', rx: 5 }, svg);
        el('rect', {
            x: 8, y: CY, width: 904, height: CH, fill: 'none',
            stroke: 'rgba(200,155,0,0.22)', 'stroke-width': 1.5, rx: 5, 'stroke-dasharray': '6 3'
        }, svg);

        // "CHECKOUT" title
        txt(svg, 'CHECKOUT', {
            x: 460, y: CY + 16,
            'text-anchor': 'middle', fill: '#c8a000',
            'font-size': 9.5, 'font-weight': 700,
            'font-family': 'Inter,sans-serif', 'letter-spacing': 3, opacity: 0.85
        });

        // 8 counter blocks
        for (let i = 0; i < 8; i++) {
            const cx = 16 + i * 112;
            const cy = CY + 26;
            // Counter body
            el('rect', { x: cx, y: cy, width: 96, height: 54, fill: '#efeff5', stroke: '#c2c2d0', 'stroke-width': 1, rx: 5 }, svg);
            // Screen
            el('rect', { x: cx + 70, y: cy + 8, width: 18, height: 22, fill: '#b8ccee', rx: 3 }, svg);
            // Belt
            el('line', { x1: cx + 6, y1: cy + 28, x2: cx + 63, y2: cy + 28, stroke: '#c4c4d4', 'stroke-width': 2.5, 'stroke-linecap': 'round' }, svg);
            // Counter number
            txt(svg, `#${i + 1}`, {
                x: cx + 20, y: cy + 20,
                fill: '#9090a8', 'font-size': 9, 'font-weight': 700,
                'font-family': 'Inter,sans-serif'
            });
            // "SCO" label under screen
            txt(svg, 'SELF', { x: cx + 79, y: cy + 38, 'text-anchor': 'middle', fill: '#9898b0', 'font-size': 6.5, 'font-family': 'Inter,sans-serif' });
            txt(svg, 'CHECKOUT', { x: cx + 79, y: cy + 47, 'text-anchor': 'middle', fill: '#9898b0', 'font-size': 6, 'font-family': 'Inter,sans-serif' });
        }

        // Service desk
        const sdx = 364, sdy = CY + 90;
        el('rect', { x: sdx, y: sdy, width: 192, height: 38, fill: '#e6e6f0', stroke: '#b0b0c8', 'stroke-width': 1.5, rx: 6 }, svg);
        txt(svg, 'SERVICE DESK', {
            x: sdx + 96, y: sdy + 23,
            'text-anchor': 'middle', fill: '#8888a8',
            'font-size': 9, 'font-weight': 600, 'font-family': 'Inter,sans-serif', 'letter-spacing': 1.5
        });
    }

    function drawEntranceExit(svg) {
        // Entrance — bottom-left of store (gap in the perimeter)
        const ENT_X = 160, EXT_X = 660;

        // Entrance arrow + label (pointing INTO the store, so arrow down from top)
        el('rect', { x: ENT_X, y: 0, width: 100, height: 5, fill: '#6C63FF', rx: 2, opacity: 0.9 }, svg);
        el('polygon', { points: `${ENT_X + 50},10 ${ENT_X + 42},0 ${ENT_X + 58},0`, fill: '#6C63FF', opacity: 0.7 }, svg);
        txt(svg, '▼  ENTRANCE', {
            x: ENT_X + 50, y: H - 10,
            'text-anchor': 'middle', fill: '#6C63FF',
            'font-size': 9, 'font-weight': 700,
            'font-family': 'Inter,sans-serif', 'letter-spacing': 1.5, opacity: 0.9
        });
        // Entrance marker at the bottom wall
        el('rect', { x: ENT_X, y: H - 5, width: 100, height: 5, fill: '#6C63FF', rx: 2, opacity: 0.9 }, svg);

        // Exit — top-right
        el('rect', { x: EXT_X, y: 0, width: 100, height: 5, fill: '#00d68f', rx: 2, opacity: 0.9 }, svg);
        el('polygon', { points: `${EXT_X + 50},15 ${EXT_X + 42},2 ${EXT_X + 58},2`, fill: '#00d68f', opacity: 0.7 }, svg);
        txt(svg, 'EXIT  ▼', {
            x: EXT_X + 50, y: H - 10,
            'text-anchor': 'middle', fill: '#00d68f',
            'font-size': 9, 'font-weight': 700,
            'font-family': 'Inter,sans-serif', 'letter-spacing': 1.5, opacity: 0.9
        });
        el('rect', { x: EXT_X, y: H - 5, width: 100, height: 5, fill: '#00d68f', rx: 2, opacity: 0.9 }, svg);
    }

    function drawPerimeter(svg) {
        el('rect', { x: 1, y: 1, width: W - 2, height: H - 2, fill: 'none', stroke: '#1a1a2e', 'stroke-width': 2.5, rx: 5 }, svg);
    }

    function buildMap() {
        const wrap = document.getElementById('store-map-wrap');
        if (!wrap) return;

        const svg = el('svg', {
            width: '100%', viewBox: `0 0 ${W} ${H}`,
            style: 'display:block;',
            role: 'img', 'aria-label': 'Supermarket sensor floor plan',
        });

        buildDefs(svg);
        el('rect', { x: 0, y: 0, width: W, height: H, fill: '#f5f5f9' }, svg);

        drawZoneFloor(svg);
        drawAisles(svg);
        SHELVES.forEach(s => drawShelf(svg, s));

        SENSOR_DEFS.forEach(sd => {
            const shelf = SHELVES[sd.shelfIdx];
            drawSensor(svg, sd.id, shelf.x + shelf.w / 2, shelf.y + sd.yOff);
        });

        drawCheckout(svg);
        drawEntranceExit(svg);
        drawPerimeter(svg);

        wrap.innerHTML = '';
        wrap.appendChild(svg);
    }

    // ===== Public API =====
    window.updateMapZoneState = function (zoneId, isWet) {
        const z = ZONE_DEFS[zoneId];
        if (!z) return;
        const floor = document.getElementById(`zone-floor-${zoneId}`);
        const border = document.getElementById(`zone-border-${zoneId}`);
        if (floor) floor.setAttribute('fill', isWet ? z.wet.fill : z.fill);
        if (border) {
            border.setAttribute('stroke', isWet ? z.wet.stroke : z.stroke);
            border.setAttribute('stroke-width', isWet ? 2.5 : 1.5);
            border.setAttribute('stroke-dasharray', isWet ? '3 2' : '6 3');
        }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', buildMap);
    } else {
        buildMap();
    }
})();
