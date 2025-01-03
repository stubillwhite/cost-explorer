import datetime
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Callable, Dict, Iterable, List

import boto3
from dateutil.relativedelta import relativedelta
from pandas import DataFrame, ExcelWriter

MONTHS_TO_REPORT = 12
FILENAME = "cost-explorer-report.xlsx"
CHART_COLUMN = "O"
CHART_HEIGHT = 42


class DataType(Enum):
    Total = auto()
    Delta = auto()


class Chart(Enum):
    Timeline = auto()
    PieChartOfLatest = auto()
    TimelineByCategory = auto()


@dataclass
class Report:
    title: str
    data: DataFrame
    charts: List[Chart]
    fmt_label: Callable[[str], str]


def _create_report(
    title: str,
    group_by: List[Dict[str, str]] = [],
    data_type: DataType = DataType.Total,
    charts: List[Chart] = [Chart.Timeline],
    fmt_label: Callable[[str], str] = lambda x: x,
) -> Report:

    client = boto3.client("ce", region_name="us-east-1")
    start = (datetime.date.today() - relativedelta(months=+MONTHS_TO_REPORT)).replace(day=1)
    end = datetime.date.today().replace(day=1)

    filter = {"Not": {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Credit", "Refund", "Upfront"]}}}

    responses = _paginate(
        client.get_cost_and_usage,
        {
            "TimePeriod": {"Start": start.isoformat(), "End": end.isoformat()},
            "Granularity": "MONTHLY",
            "Metrics": ["UnblendedCost"],
            "GroupBy": group_by,
            "Filter": filter,
        },
    )

    data = [result for response in responses for result in response["ResultsByTime"]]
    df = _create_dataframe(data, data_type, fmt_label)

    return Report(title, df, charts, fmt_label)


def _paginate(f: Callable[[Any], Any], config: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    while True:
        r = f(**config)  # type: ignore[call-arg]
        yield r

        if "nextToken" in r:
            config["NextPageToken"] = r["nextToken"]
        else:
            return None


def _create_dataframe(data: List[Dict[str, Any]], data_type: DataType, fmt_label: Callable[[str], str]) -> DataFrame:
    rows = []
    sort = ""
    for d in data:
        row = {"date": d["TimePeriod"]["Start"]}
        sort = d["TimePeriod"]["Start"]

        if not d["Groups"]:
            row["Total"] = float(d["Total"]["UnblendedCost"]["Amount"])

        else:
            for group in d["Groups"]:
                key = fmt_label(group["Keys"][0])
                row[key] = float(group["Metrics"]["UnblendedCost"]["Amount"])

        rows.append(row)

    df = DataFrame(rows)
    df.set_index("date", inplace=True)
    df = df.fillna(0.0)

    if data_type == DataType.Delta:
        df = _calculate_deltas(df)

    df = df.T
    df = df.sort_values(sort, ascending=False)

    return df


def _calculate_deltas(df: DataFrame) -> DataFrame:
    deltas = df.copy()
    prev_idx = None

    for idx, row in df.iterrows():
        for i in row.index:
            if prev_idx:
                deltas.at[idx, i] = df.at[idx, i] - df.at[prev_idx, i]
            else:
                deltas.at[idx, i] = 0
        prev_idx = idx

    return deltas


# TODO: Conditional formatting
# TODO: Function to transform names (for SubProduct$value labels)
def _export_reports(reports: List[Report]) -> None:
    fnam = FILENAME

    print(f"Creating {fnam}")

    with ExcelWriter(fnam, engine="xlsxwriter") as writer:
        workbook = writer.book

        for report in reports:
            print(f" - adding {report.title}")

            report.data.to_excel(writer, sheet_name=report.title)
            worksheet = writer.sheets[report.title]

            _insert_charts(workbook, worksheet, report)

            # (max_row, max_col) = report.data.shape
            # worksheet.conditional_format(1, 1, max_row, max_col, {"type": "3_color_scale"})


def _insert_charts(workbook, worksheet, report: Report) -> None:

    chart_row = 2

    # Timeline
    if Chart.Timeline in report.charts:
        timeline_chart = workbook.add_chart({"type": "column", "subtype": "stacked"})

        for row_num in range(1, len(report.data) + 1):
            timeline_chart.add_series(
                {
                    "name": [report.title, row_num, 0],
                    "categories": [report.title, 0, 1, 0, MONTHS_TO_REPORT],
                    "values": [report.title, row_num, 1, row_num, MONTHS_TO_REPORT],
                }
            )

        timeline_chart.set_y_axis({"label_position": "low"})
        timeline_chart.set_x_axis({"label_position": "low"})
        worksheet.insert_chart(f"{CHART_COLUMN}{chart_row}", timeline_chart, {"x_scale": 2.0, "y_scale": 2.0})

        chart_row += CHART_HEIGHT

    # Timeline with category
    if Chart.TimelineByCategory in report.charts:
        line_chart = workbook.add_chart({"type": "line"})

        for row_num in range(1, len(report.data) + 1):
            line_chart.add_series(
                {
                    "name": [report.title, row_num, 0],
                    "categories": [report.title, 0, 1, 0, MONTHS_TO_REPORT],
                    "values": [report.title, row_num, 1, row_num, MONTHS_TO_REPORT],
                }
            )

        line_chart.set_y_axis({"label_position": "low"})
        line_chart.set_x_axis({"label_position": "low"})
        worksheet.insert_chart(f"{CHART_COLUMN}{chart_row}", line_chart, {"x_scale": 2.0, "y_scale": 2.0})

        chart_row += CHART_HEIGHT

    # Pie chart
    if Chart.PieChartOfLatest in report.charts:
        pie_chart = workbook.add_chart({"type": "pie"})

        pie_chart.add_series(
            {
                "name": [report.title, 0, MONTHS_TO_REPORT],
                "categories": [report.title, 1, 0, len(report.data), 0],
                "values": [report.title, 1, MONTHS_TO_REPORT, len(report.data), MONTHS_TO_REPORT],
            }
        )

        pie_chart.set_y_axis({"label_position": "low"})
        pie_chart.set_x_axis({"label_position": "low"})
        worksheet.insert_chart(f"{CHART_COLUMN}{chart_row}", pie_chart, {"x_scale": 2.0, "y_scale": 2.0})

        chart_row += CHART_HEIGHT


def strip_prefix(prefix: str) -> Callable[[str], str]:
    def strip(s: str) -> str:
        return s.replace(prefix, "", 1) 

    return strip


def main() -> None:
    # fmt: off
    reports = [
        _create_report("Total",            data_type=DataType.Total),
        _create_report("TotalChange",      data_type=DataType.Delta),
        _create_report("SubProduct",       group_by=[{"Type": "TAG",       "Key": "SubProduct"}], data_type=DataType.Total, charts=[Chart.PieChartOfLatest], fmt_label=strip_prefix("SubProduct$")),
        _create_report("Services",         group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}],    data_type=DataType.Total, charts=[Chart.PieChartOfLatest]),
        _create_report("ServicesChange",   group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}],    data_type=DataType.Delta, charts=[Chart.TimelineByCategory]),
        _create_report("Regions",          group_by=[{"Type": "DIMENSION", "Key": "REGION"}],     data_type=DataType.Total, charts=[Chart.PieChartOfLatest]),
        _create_report("RegionsChange",    group_by=[{"Type": "DIMENSION", "Key": "REGION"}],     data_type=DataType.Delta, charts=[Chart.TimelineByCategory]),
    ]
    # fmt: on

    _export_reports(reports)
