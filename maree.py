import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
from io import StringIO
import locale
import json


def get_sun_times(start_date: datetime, end_date: datetime) -> list:
    gps_lat: str = "50.216569"
    gps_lng: str = "1.624047"
    timezone: str = "CET"
    params: dict = {
        "lat": gps_lat,
        "lng": gps_lng,
        "timezone": timezone,
        "date_start": start_date.strftime("%Y-%m-%d"),
        "date_end": end_date.strftime("%Y-%m-%d"),
        "time_format": "24",
    }

    # get the sunrise and sunset time
    timeurl: str = "https://api.sunrisesunset.io/json"
    response: requests.Response = requests.get(timeurl, params=params)
    if response.status_code != 200:
        print("error while requesting sun times")
        exit(-200)
    res = json.loads(response.content)
    print("sun times recieved")
    return res["results"]


def get_tide_data(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    tide_headers = {
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Cookie": "UserAgreement=cf60bb9aab1a573ca00bf3d30f1026bede914adc7cbea51c4cb762f729b66eed270d7376; PHPSESSID=o93rg22kcf4varpc7nasktfes1",
    }

    delta: timedelta = timedelta(days=7)
    df_html_tables: list = []

    # Get the tide info by weeks and join them
    current_date: datetime = start_date
    while current_date <= end_date:
        # Récupérer la page web pour le jour actuel (URL et méthode d'accès à ajuster selon le site)
        tide_params: dict = {"d": current_date.strftime("%Y%m%d")}
        tide_url: str = "https://maree.info/150"
        response: requests.Response = requests.get(
            tide_url, headers=tide_headers, params=tide_params
        )

        soup = BeautifulSoup(response.content, "html.parser")

        for tide in soup.find_all(id="MareeJours"):
            string_table = StringIO(str(tide))
            df_html_table: pd.DataFrame = pd.read_html(string_table)[0]

        # ingore week/rows with "Changement d'heure"
        df_html_table.drop(
            df_html_table[df_html_table["Date"].str.contains("Changement")].index,
            inplace=True,
        )

        df_html_tables.append(df_html_table)

        current_date += delta
        print(current_date)
    return pd.concat(df_html_tables, ignore_index=True)


def join_tide_sun_data(
    start_date: datetime,
    end_date: datetime,
    df_year_tides: pd.DataFrame,
    year_sun_times: list,
) -> pd.DataFrame:
    tide_dics: list[dict] = []
    # iter on rows of week
    current_date: datetime = start_date
    delta: timedelta = timedelta(days=1)
    for row, sun_time in zip(df_year_tides.iterrows(), year_sun_times):
        # Compute a date like "Name_of_the_day DD Name_of_the_month YYYY"
        date: str = current_date.strftime("%A %d %B %Y")

        values = row[1].to_numpy()
        _, hours, heights, coefficients = values
        # print(date)

        heights: list[str] = heights.split(" ")
        hours: list[str] = hours.replace("h", ":").split(" ")
        coefficients: list[str] = list(filter(lambda x: len(x) > 0, coefficients.split(" ")))

        # print(heights)
        number_heigts: list[float] = list(map(lambda x: float(x[:-1].replace(",", ".")), heights))
        if number_heigts[0] > number_heigts[1]:
            # high tide first
            coefficients.insert(1, "")
            coefficients.insert(3, "")
        else:
            # high tide second
            coefficients.insert(0, "")
            coefficients.insert(2, "")

        sunrise, sunset = sun_time["sunrise"][:-3], sun_time["sunset"][:-3]
        # print(sunrise, sunset)

        day: list[dict] = []
        for hour, height, coefficient in zip(hours, heights, coefficients):
            # add sunrise and sunset time
            # tide = (date, hour, height, coefficient, sunrise, sunset)
            tide: dict = {
                "date": date,
                "coefficient": coefficient,
                "hauteur": height,
                "pleine mer": hour,
                "lever du soleil": sunrise,
                "coucher du soleil": sunset,
            }
            day.append(tide)

        # drop low tides
        day = list(filter(lambda x: x["coefficient"] != "", day))

        tide_dics.extend(day)
        current_date += delta
    return pd.DataFrame(tide_dics)


def get_minutes_from_time(time: str) -> int:
    """
    inputs
    time is a string hh:mm
    ouputs
    the number of minutes in time
    """
    hours = int(time[:2])
    minutes = int(time[-2:])
    return 60 * hours + minutes


def time_by_coefficient_at_day(row: pd.Series):
    """
    inputs
    row: a row from the dataset
    outputs
    the time as a string hh:mm or "NUIT"
    """
    sunrise: int = get_minutes_from_time(row["lever du soleil"])
    sunset: int = get_minutes_from_time(row["coucher du soleil"])
    time: int = get_minutes_from_time(row["pleine mer"])
    coefficient = int(row["coefficient"])
    delta: int = 0

    if coefficient > 0 and coefficient <= 40:
        delta = -30
    elif coefficient > 40 and coefficient <= 60:
        delta = -15
    elif coefficient > 60 and coefficient < 80:
        delta = 0
    elif coefficient >= 80 and coefficient < 90:
        delta = 15
    elif coefficient >= 90 and coefficient < 100:
        delta = 30
    elif coefficient >= 100 and coefficient < 110:
        delta = 45
    elif coefficient >= 110:
        delta = 60
    else:
        return "ERROR could not compute hour"

    time = time + delta
    hours: int = time // 60
    minutes: int = time % 60

    # return time if at day else night
    if time >= sunrise - 15 and time <= sunset - 45:
        return f"{hours:02}:{minutes:02}"
    else:
        return "NUIT"


output_filename: str = "marees_le_crotoy_2025.xlsx"
locale.setlocale(locale.LC_ALL, "fr_FR")
# Définir les dates
start_date: datetime = datetime(2025, 1, 1)
end_date: datetime = datetime(2025, 12, 31)

sun_times: list = get_sun_times(start_date, end_date)

joined_tide_tables: pd.DataFrame = get_tide_data(start_date, end_date)

df: pd.DataFrame = join_tide_sun_data(start_date, end_date, joined_tide_tables, sun_times)

df["heure de sortie"] = df.apply(time_by_coefficient_at_day, axis=1)
# df.drop(df[df["heure de sortie"] == "NUIT"].index, inplace=True)

new_order: list[str] = df.columns.to_list()
exit_time: str = new_order.pop()
new_order.insert(1, exit_time)

df = df[new_order]
df.to_excel(output_filename, index=False)
