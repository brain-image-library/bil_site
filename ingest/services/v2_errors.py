"""Normalize outputs of validate_spreadsheet + check_all_sheets to a shared shape."""


def normalize_errors(spreadsheet_errors, spreadsheet_warnings, cell_error_map):
    workbook = [{'level': 'error', 'message': m} for m in spreadsheet_errors]
    workbook += [{'level': 'warning', 'message': m} for m in spreadsheet_warnings]

    cells = []
    for key, messages in cell_error_map.items():
        sheet_name, row_str, col_str = key.split('::')
        row, col = int(row_str), int(col_str)
        for msg in messages:
            cells.append({'sheet': sheet_name, 'row': row, 'col': col, 'message': msg})

    has_blocking = any(w['level'] == 'error' for w in workbook) or bool(cells)
    return {'workbook': workbook, 'cells': cells, 'has_blocking': has_blocking}
