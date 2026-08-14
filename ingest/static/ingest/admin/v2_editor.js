(function () {
    const data = {
        workbook: JSON.parse(document.getElementById('v2-workbook-json').textContent),
        errorCells: JSON.parse(document.getElementById('v2-error-cells-json').textContent)
    };

    const sheetData = data.workbook.map((s, idx) => ({
        name: s.name,
        celldata: s.celldata,
        index: String(idx),
        status: idx === 0 ? 1 : 0,
        order: idx
    }));

    luckysheet.create({
        container: 'luckysheet',
        data: sheetData,
        showtoolbar: true,
        showinfobar: false,
        showsheetbar: true,
        showstatisticBar: false,
        allowUpdate: true,
        enableAddRow: true,
        enableAddBackTop: false,
        hook: {
            workbookCreateAfter() {
                highlightErrorCells();
            }
        }
    });

    function highlightErrorCells() {
        (data.errorCells || []).forEach(function (c) {
            const sheetIndex = data.workbook.findIndex(s => s.name === c.sheet);
            if (sheetIndex < 0) return;
            luckysheet.setCellFormat(c.row, c.col, 'bg', '#ffdddd', { order: sheetIndex });
        });
    }

    document.querySelectorAll('.cell-jump').forEach(function (a) {
        a.addEventListener('click', function (e) {
            e.preventDefault();
            const sheet = a.dataset.sheet;
            const row = parseInt(a.dataset.row, 10);
            const col = parseInt(a.dataset.col, 10);
            const idx = data.workbook.findIndex(s => s.name === sheet);
            if (idx >= 0) {
                luckysheet.setSheetActive(idx);
                luckysheet.setRangeShow({ row: [row, row], column: [col, col] });
            }
        });
    });

    document.getElementById('save-btn').addEventListener('click', function () {
        const allSheets = luckysheet.getAllSheets();
        const payload = allSheets.map(function (s) {
            const cells = [];
            (s.celldata || []).forEach(function (cd) {
                if (cd && cd.v && (cd.v.v !== undefined && cd.v.v !== '')) {
                    cells.push({ r: cd.r, c: cd.c, v: { v: cd.v.v, m: String(cd.v.m || cd.v.v) } });
                }
            });
            return { name: s.name, celldata: cells };
        });
        document.getElementById('workbook-input').value = JSON.stringify(payload);
        document.getElementById('save-form').submit();
    });
})();
