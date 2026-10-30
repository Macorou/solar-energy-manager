"""Spreadsheet-safe UTF-8 CSV and dependency-free Office Open XML export."""
import csv
import io
import re
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

HEADERS = ['Début','Fin','Point de charge','Véhicule','Énergie (kWh)','Durée de charge (s)',
    'Solaire (kWh)','Réseau (kWh)','Origine inconnue (kWh)','Solaire (%)','Coût (EUR)',
    'Prix moyen (EUR/kWh)','Énergie partielle','Coût partiel','Durée partielle','En cours']
KEYS = ['started_at','ended_at','device_name','vehicle_name','energy_kwh','charge_duration_s',
    'solar_kwh','grid_kwh','unknown_kwh','solar_percent','cost_eur','average_price_per_kwh',
    'energy_partial','cost_partial','duration_partial','active']


def safe_text(value):
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(value))
    return "'"+text if text.lstrip().startswith(('=','+','-','@','\t','\r')) else text


def export_rows(rows):
    yield HEADERS
    for row in rows:
        yield [None if row.get(k) is None else 'oui' if row[k] is True else 'non' if row[k] is False
            else row[k] for k in KEYS]


def csv_export(rows):
    output = io.StringIO(newline=''); writer = csv.writer(output, delimiter=';')
    yield '\ufeff'
    for row in export_rows(rows):
        writer.writerow([safe_text(v) if isinstance(v,str) else '' if v is None else str(v).replace('.',',') for v in row])
        yield output.getvalue(); output.seek(0); output.truncate(0)


def xlsx_export(rows):
    def column(n):
        result=''
        while n: n, rem = divmod(n-1, 26); result=chr(65+rem)+result
        return result
    sheet = io.StringIO(); sheet.write('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>')
    for number,row in enumerate(export_rows(rows), 1):
        sheet.write(f'<row r="{number}">')
        for index, value in enumerate(row, 1):
            if value is None: continue
            ref = column(index)+str(number)
            if isinstance(value,(float,int)):
                sheet.write(f'<c r="{ref}"><v>{value}</v></c>')
            else:sheet.write(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(safe_text(value))}</t></is></c>')
        sheet.write('</row>')
    sheet.write('</sheetData></worksheet>')
    output=io.BytesIO()
    with ZipFile(output,'w',ZIP_DEFLATED) as doc:
        doc.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        doc.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        doc.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sessions" sheetId="1" r:id="rId1"/></sheets></workbook>')
        doc.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        doc.writestr('xl/worksheets/sheet1.xml',sheet.getvalue())
    return output.getvalue()
