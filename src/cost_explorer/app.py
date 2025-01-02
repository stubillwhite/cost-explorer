import datetime
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Callable, Dict, Iterable, List

import boto3
from dateutil.relativedelta import relativedelta
from pandas import DataFrame, ExcelWriter

# Constants
MONTHS_TO_REPORT = 6
FILENAME = "cost_explorer_report_white.xlsx"

class DataType(Enum):
    Total = auto()
    Delta = auto()


@dataclass
class Report:
    title: str
    data: DataFrame


def _create_report(title: str, group_by: List[Dict[str, str]] = [], data_type: DataType = DataType.Total) -> Report:

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
    df = _create_dataframe(data, data_type)

    return Report(title, df)


def _paginate(f: Callable[[Any], Any], config: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    while True:
        r = f(**config)  # type: ignore[call-arg]
        yield r

        if "nextToken" in r:
            config["NextPageToken"] = r["nextToken"]
        else:
            return None


def _create_dataframe(data: List[Dict[str, Any]], data_type: DataType) -> DataFrame:
    rows = []
    sort = ""
    for d in data:
        row = {"date": d["TimePeriod"]["Start"]}
        sort = d["TimePeriod"]["Start"]

        if not d["Groups"]:
            row["Total"] = float(d["Total"]["UnblendedCost"]["Amount"])

        else:
            for group in d["Groups"]:
                key = group["Keys"][0]
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
    # TODO: Clean up
    deltas = df.copy()
    prev_idx = None
    for idx, row in df.iterrows():
        if prev_idx:
            for i in row.index:
                deltas.at[idx, i] = df.at[idx, i] - df.at[prev_idx, i]
        prev_idx = idx

    print(deltas)
    return deltas


def _export_reports(reports: List[Report]) -> None:
    fnam = FILENAME 

    print(f"Creating {fnam}")

    with ExcelWriter(fnam, engine="xlsxwriter") as writer:
        workbook = writer.book

        for report in reports:
            print(f" - adding {report.title}")

            report.data.to_excel(writer, sheet_name=report.title)
            worksheet = writer.sheets[report.title]

            chart = workbook.add_chart({"type": "column", "subtype": "stacked"})

            for row_num in range(1, len(report.data) + 1):
                chart.add_series(
                    {
                        "name": [report.title, row_num, 0],
                        "categories": [report.title, 0, 1, 0, MONTHS_TO_REPORT],
                        "values": [report.title, row_num, 1, row_num, MONTHS_TO_REPORT],
                    }
                )

            chart.set_y_axis({"label_position": "low"})
            chart.set_x_axis({"label_position": "low"})
            worksheet.insert_chart("O2", chart, {"x_scale": 2.0, "y_scale": 2.0})


def main() -> None:
    # fmt: off
    reports = [
        #  _create_report("Total",            data_type=DataType.Total),
        _create_report("TotalChange",      data_type=DataType.Delta),
        #  _create_report("SubProduct",       group_by=[{"Type": "TAG",       "Key": "SubProduct"}], data_type=DataType.Total),
        #  _create_report("SubProductChange", group_by=[{"Type": "TAG",       "Key": "SubProduct"}], data_type=DataType.Delta),
        #  _create_report("Services",         group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}],    data_type=DataType.Total),
        #  _create_report("ServicesChange",   group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}],    data_type=DataType.Delta),
        #  _create_report("Regions",          group_by=[{"Type": "DIMENSION", "Key": "REGION"}],     data_type=DataType.Total),
        #  _create_report("RegionsChange",    group_by=[{"Type": "DIMENSION", "Key": "REGION"}],     data_type=DataType.Delta),
    ]
    # fmt: on

    _export_reports(reports)

    #  main_handler()
