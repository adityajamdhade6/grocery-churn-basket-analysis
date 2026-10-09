"""Attaches two native Excel PivotTables to excel/Instacart_Basket_Analysis.xlsx (sheet Pivot_Basket), built on Orders_Data.
xlsxwriter and openpyxl cannot create PivotTables, so the PivotTable parts are written directly into the .xlsx package.
The cache is set to refresh on open, so Excel recalculates both tables from Orders_Data the first time the file is opened."""
import re, shutil, zipfile
from pathlib import Path
import openpyxl

root = Path(__file__).resolve().parent.parent
path = root / "excel" / "Instacart_Basket_Analysis.xlsx"
NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

ws = openpyxl.load_workbook(path, read_only=True)["Orders_Data"]
rows = list(ws.iter_rows(min_row=1, values_only=True)); head, data = list(rows[0]), rows[1:]; N = len(data)
STAGES = ["1st order", "2nd-4th", "5th-9th", "10th-19th", "20th+"]
TIMES = ["Morning (6-11h)", "Afternoon (12-17h)", "Evening (18-23h)", "Night (0-5h)"]
assert head == ["order_id", "user_id", "order_number", "hour_of_day", "basket_size", "reordered_items", "order_stage", "time_of_day"]

def cache_def():
    f = []
    for i, name in enumerate(head):
        col = [r[i] for r in data]
        if name == "order_stage":   f.append(f'<cacheField name="{name}" numFmtId="0"><sharedItems count="5">' + "".join(f'<s v="{v}"/>' for v in STAGES) + "</sharedItems></cacheField>")
        elif name == "time_of_day": f.append(f'<cacheField name="{name}" numFmtId="0"><sharedItems count="4">' + "".join(f'<s v="{v}"/>' for v in TIMES) + "</sharedItems></cacheField>")
        else: f.append(f'<cacheField name="{name}" numFmtId="0"><sharedItems containsSemiMixedTypes="0" containsString="0" containsNumber="1" containsInteger="1" minValue="{min(col)}" maxValue="{max(col)}"/></cacheField>')
    f.append('<cacheField name="repeat_share" numFmtId="0" formula="reordered_items/basket_size" databaseField="0"/>')
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<pivotCacheDefinition {NS} refreshOnLoad="1" refreshedBy="Analyst" refreshedDate="45000" '
            f'createdVersion="6" refreshedVersion="6" minRefreshableVersion="3" recordCount="{N}" saveData="0">'
            f'<cacheSource type="worksheet"><worksheetSource ref="A1:H{N+1}" sheet="Orders_Data"/></cacheSource><cacheFields count="9">{"".join(f)}</cacheFields></pivotCacheDefinition>')

def pivot_def(name, ref, row_field, items):
    n = len(items); pf = []
    for i in range(9):
        if i == row_field: pf.append('<pivotField axis="axisRow" showAll="0"><items count="%d">%s<item t="default"/></items></pivotField>' % (n + 1, "".join(f'<item x="{k}"/>' for k in range(n))))
        elif i in (0, 4): pf.append('<pivotField dataField="1" showAll="0"/>')
        elif i == 8: pf.append('<pivotField dataField="1" dragToRow="0" dragToCol="0" dragToPage="0" showAll="0" defaultSubtotal="0"/>')
        else: pf.append('<pivotField showAll="0"/>')
    ri = "".join('<i><x/></i>' if k == 0 else f'<i><x v="{k}"/></i>' for k in range(n)) + '<i t="grand"><x/></i>'
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<pivotTableDefinition {NS} name="{name}" cacheId="1" applyNumberFormats="0" applyBorderFormats="0" '
            f'applyFontFormats="0" applyPatternFormats="0" applyAlignmentFormats="0" applyWidthHeightFormats="1" dataCaption="Values" updatedVersion="6" minRefreshableVersion="3" '
            f'useAutoFormatting="1" itemPrintTitles="1" createdVersion="6" indent="0" outline="1" outlineData="1" multipleFieldFilters="0">'
            f'<location ref="{ref}" firstHeaderRow="0" firstDataRow="1" firstDataCol="1"/><pivotFields count="9">{"".join(pf)}</pivotFields>'
            f'<rowFields count="1"><field x="{row_field}"/></rowFields><rowItems count="{n+1}">{ri}</rowItems>'
            f'<colFields count="1"><field x="-2"/></colFields><colItems count="3"><i><x/></i><i i="1"><x v="1"/></i><i i="2"><x v="2"/></i></colItems>'
            f'<dataFields count="3"><dataField name="Orders" fld="0" subtotal="count" baseField="0" baseItem="0" numFmtId="3"/>'
            f'<dataField name="Avg basket size" fld="4" subtotal="average" baseField="0" baseItem="0" numFmtId="2"/>'
            f'<dataField name="Repeat share of basket" fld="8" baseField="0" baseItem="0" numFmtId="10"/></dataFields>'
            f'<pivotTableStyleInfo name="PivotStyleLight1" showRowHeaders="1" showColHeaders="1" showRowStripes="0" showColStripes="0" showLastColumn="1"/></pivotTableDefinition>')

tmp = path.with_suffix(".tmp")
with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        b = zin.read(item.filename)
        if item.filename == "[Content_Types].xml":
            t = b.decode().replace("</Types>", '<Override PartName="/xl/pivotCache/pivotCacheDefinition1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheDefinition+xml"/>'
                + "".join(f'<Override PartName="/xl/pivotTables/pivotTable{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotTable+xml"/>' for i in (1, 2)) + "</Types>")
            b = t.encode()
        elif item.filename == "xl/workbook.xml":
            t = b.decode(); assert "<pivotCaches" not in t
            t = re.sub(r"(<calcPr[^>]*/>)", r'\1<pivotCaches><pivotCache cacheId="1" r:id="rIdPivotCache1"/></pivotCaches>', t, count=1); assert "pivotCaches" in t
            b = t.encode()
        elif item.filename == "xl/_rels/workbook.xml.rels":
            b = b.decode().replace("</Relationships>", f'<Relationship Id="rIdPivotCache1" Type="{REL}/pivotCacheDefinition" Target="pivotCache/pivotCacheDefinition1.xml"/></Relationships>').encode()
        elif item.filename == "xl/worksheets/_rels/sheet2.xml.rels":
            b = b.decode().replace("</Relationships>", "".join(f'<Relationship Id="rIdPivot{i}" Type="{REL}/pivotTable" Target="../pivotTables/pivotTable{i}.xml"/>' for i in (1, 2)) + "</Relationships>").encode()
        zout.writestr(item, b)
    zout.writestr("xl/pivotCache/pivotCacheDefinition1.xml", cache_def())
    zout.writestr("xl/pivotTables/pivotTable1.xml", pivot_def("PivotByStage", "A4:D10", 6, STAGES))
    zout.writestr("xl/pivotTables/pivotTable2.xml", pivot_def("PivotByTimeOfDay", "A13:D18", 7, TIMES))
    for i in (1, 2):
        zout.writestr(f"xl/pivotTables/_rels/pivotTable{i}.xml.rels", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{REL}/pivotCacheDefinition" Target="../pivotCache/pivotCacheDefinition1.xml"/></Relationships>')
shutil.move(tmp, path); print("pivot tables attached")
